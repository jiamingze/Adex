import {Capacitor,registerPlugin} from '@capacitor/core';
import {Camera,CameraResultType,CameraSource} from '@capacitor/camera';
const secure=registerPlugin<{get():Promise<{token:string}>;set(input:{token:string}):Promise<void>;clear():Promise<void>}>('SecureSession');
import {cloudSpeech,releaseCloudSpeech,browserCapture,speechConnection} from './cloudSpeech';
const speech=registerPlugin<{start(input:{session_id:string}):Promise<void>;connect(input:{session_id:string;url:string;token:string}):Promise<{text:string}>;stop(input:{session_id:string}):Promise<void>;cancel(input:{session_id:string}):Promise<void>;addListener(name:'partial',callback:(event:{session_id:string;text:string})=>void):Promise<{remove():Promise<void>}>}>('AdexSpeech');
export const native=Capacitor.isNativePlatform();
if(native)document.documentElement.classList.add("native-app");
export async function loadSession(){return native?(await secure.get()).token:'';}
export async function saveSession(token:string){if(native)await secure.set({token});}
export async function clearSession(){if(native)await secure.clear();}
export async function photo(cameraOnly=false){const p=await Camera.getPhoto({source:cameraOnly?CameraSource.Camera:CameraSource.Photos,resultType:CameraResultType.Uri,quality:85});if(!p.webPath)throw new Error('PHOTO_UNAVAILABLE');const r=await fetch(p.webPath);if(!r.ok)throw new Error('PHOTO_UNAVAILABLE');const b=await r.blob();return new File([b],'photo.'+p.format,{type:b.type||'image/'+p.format});}
let nativeGesture:{id:string;released:boolean;cancelled:boolean}|undefined;
export async function transcribe(onPartial?:(text:string)=>void){
 if(!native)return cloudSpeech(browserCapture,onPartial);
 if(nativeGesture)throw new Error('SPEECH_BUSY');
 const gesture={id:crypto.randomUUID(),released:false,cancelled:false};nativeGesture=gesture;
 let listener:{remove():Promise<void>}|undefined;
 try{
  listener=await speech.addListener('partial',event=>{if(event.session_id===gesture.id&&!gesture.released&&!gesture.cancelled)onPartial?.(event.text);});
  if(gesture.released)return '';
  const [,connection]=await Promise.all([speech.start({session_id:gesture.id}),speechConnection()]);
  if(gesture.cancelled)return '';
  return (await speech.connect({session_id:gesture.id,...connection})).text;
 }catch(error){if(gesture.released&&String(error).includes('CANCELLED'))return '';throw error;}
 finally{await speech.cancel({session_id:gesture.id});await listener?.remove();if(nativeGesture===gesture)nativeGesture=undefined;}
}
export async function stopSpeech(cancel=false){
 if(nativeGesture){nativeGesture.released=true;nativeGesture.cancelled=cancel;await (cancel?speech.cancel({session_id:nativeGesture.id}):speech.stop({session_id:nativeGesture.id}));}
 else releaseCloudSpeech(cancel);
}


if(native){window.addEventListener("keyboardWillShow",()=>document.documentElement.classList.add("keyboard-open"));window.addEventListener("keyboardWillHide",()=>document.documentElement.classList.remove("keyboard-open"));}

const push = registerPlugin<{request(input?:{prompt:boolean}):Promise<{token:string;environment:"sandbox"|"production"}>;pending():Promise<{notification_id:string}>;acknowledge():Promise<void>;addListener(name:string,callback:(event:{notification_id:string})=>void):Promise<{remove():Promise<void>}>}>('AdexPush');
export async function requestPush(prompt=true){if(!native)throw new Error('请在 iOS 客户端授权通知');return await push.request({prompt});}
export function listenPush(handler:(id:string)=>Promise<void>){
 if(!native)return ()=>{};
 let disposed=false,subscription:{remove():Promise<void>}|undefined;
 const process=async(event:{notification_id:string})=>{if(disposed||!event.notification_id)return;await handler(event.notification_id);await push.acknowledge();};
 push.addListener('tap',event=>{process(event).catch(()=>{});}).then(value=>{if(disposed)value.remove();else subscription=value;}).catch(()=>{});
 push.pending().then(process).catch(()=>{});
 return ()=>{disposed=true;subscription?.remove();};
}
