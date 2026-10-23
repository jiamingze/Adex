import {Capacitor,registerPlugin} from '@capacitor/core';
import {Camera,CameraResultType,CameraSource} from '@capacitor/camera';
const secure=registerPlugin<{get():Promise<{token:string}>;set(input:{token:string}):Promise<void>;clear():Promise<void>}>('SecureSession');
import {cloudSpeech,releaseCloudSpeech,browserCapture,type SpeechCapture} from './cloudSpeech';
const speech=registerPlugin<{start(input:{session_id:string}):Promise<void>;stop(input:{session_id:string}):Promise<void>;addListener(name:'audio',callback:(event:{session_id:string;pcm:string})=>void):Promise<{remove():Promise<void>}>}>('AdexSpeech');
export const native=Capacitor.isNativePlatform();
if(native)document.documentElement.classList.add("native-app");
export async function loadSession(){return native?(await secure.get()).token:'';}
export async function saveSession(token:string){if(native)await secure.set({token});}
export async function clearSession(){if(native)await secure.clear();}
export async function photo(cameraOnly=false){const p=await Camera.getPhoto({source:cameraOnly?CameraSource.Camera:CameraSource.Photos,resultType:CameraResultType.Uri,quality:85});if(!p.webPath)throw new Error('PHOTO_UNAVAILABLE');const r=await fetch(p.webPath);if(!r.ok)throw new Error('PHOTO_UNAVAILABLE');const b=await r.blob();return new File([b],'photo.'+p.format,{type:b.type||'image/'+p.format});}
const nativeCapture:SpeechCapture=async (audio,signal)=>{
 const id=crypto.randomUUID();
 const listener=await speech.addListener('audio',event=>{if(event.session_id!==id)return;const bytes=Uint8Array.from(atob(event.pcm),char=>char.charCodeAt(0));audio(bytes.buffer);});
 const cancel=()=>{void speech.stop({session_id:id});};
 signal.addEventListener('abort',cancel,{once:true});
 try{if(signal.aborted)throw new Error('SPEECH_CANCELLED');await speech.start({session_id:id});}catch(error){signal.removeEventListener('abort',cancel);await listener.remove();throw error;}
 return async()=>{signal.removeEventListener('abort',cancel);await speech.stop({session_id:id});await listener.remove();};
};
export async function transcribe(onPartial?:(text:string)=>void){return cloudSpeech(native?nativeCapture:browserCapture,onPartial);}
export async function stopSpeech(cancel=false){releaseCloudSpeech(cancel);}


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
