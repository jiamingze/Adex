import {Capacitor,registerPlugin} from '@capacitor/core';
import {Camera,CameraResultType,CameraSource} from '@capacitor/camera';
const secure=registerPlugin<{get():Promise<{token:string}>;set(input:{token:string}):Promise<void>;clear():Promise<void>}>('SecureSession');
const speech=registerPlugin<{start(input:{session_id:string}):Promise<{text:string}>;stop(input:{session_id:string}):Promise<void>;addListener(name:'partial',callback:(event:{session_id:string;text:string})=>void):Promise<{remove():Promise<void>}>}>('AdexSpeech');
export const native=Capacitor.isNativePlatform();
if(native)document.documentElement.classList.add("native-app");
export async function loadSession(){return native?(await secure.get()).token:'';}
export async function saveSession(token:string){if(native)await secure.set({token});}
export async function clearSession(){if(native)await secure.clear();}
export async function photo(cameraOnly=false){const p=await Camera.getPhoto({source:cameraOnly?CameraSource.Camera:CameraSource.Photos,resultType:CameraResultType.Uri,quality:85});if(!p.webPath)throw new Error('PHOTO_UNAVAILABLE');const r=await fetch(p.webPath);if(!r.ok)throw new Error('PHOTO_UNAVAILABLE');const b=await r.blob();return new File([b],'photo.'+p.format,{type:b.type||'image/'+p.format});}
let nativeSpeechId:string|undefined;
let browserSpeech:{stop():void}|undefined;
export async function transcribe(onPartial?:(text:string)=>void){
 if(native){
  const id=crypto.randomUUID();nativeSpeechId=id;
  let listener:{remove():Promise<void>}|undefined;
  try{
   listener=await speech.addListener('partial',event=>{if(nativeSpeechId===id&&event.session_id===id)onPartial?.(event.text);});
   return (await speech.start({session_id:id})).text;
  }
  finally{if(nativeSpeechId===id)nativeSpeechId=undefined;await listener?.remove();}
 }
 const ctor=(window as unknown as {SpeechRecognition?:new()=>any;webkitSpeechRecognition?:new()=>any}).SpeechRecognition||(window as unknown as {webkitSpeechRecognition?:new()=>any}).webkitSpeechRecognition;
 if(!ctor)throw new Error('此浏览器不支持语音识别，请使用 iOS 客户端。');
 return new Promise<string>((resolve,reject)=>{
  const recognizer=new ctor();browserSpeech=recognizer;let text='',settled=false;
  const timer=setTimeout(()=>recognizer.stop(),45000);
  const finish=(error?:Error)=>{if(settled)return;settled=true;clearTimeout(timer);browserSpeech=undefined;error?reject(error):resolve(text);};
  recognizer.lang='zh-CN';recognizer.interimResults=true;recognizer.continuous=true;
  recognizer.onresult=(event:any)=>{text=Array.from(event.results as any[]).map((result:any)=>result[0].transcript).join('');if(!settled)onPartial?.(text);};
  recognizer.onerror=(event:any)=>finish(new Error(event.error==='not-allowed'?'MICROPHONE_PERMISSION_DENIED':'语音识别暂不可用，请重试'));
  recognizer.onend=()=>finish();
  try{recognizer.start();}catch(error){finish(error instanceof Error?error:new Error('语音识别无法启动'));}
 });
}
export async function stopSpeech(){if(native){const id=nativeSpeechId;if(id)await speech.stop({session_id:id});}else browserSpeech?.stop();}


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
