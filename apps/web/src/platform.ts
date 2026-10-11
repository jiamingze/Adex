import {Capacitor,registerPlugin} from '@capacitor/core';
import {Camera,CameraResultType,CameraSource} from '@capacitor/camera';
const secure=registerPlugin<{get():Promise<{token:string}>;set(input:{token:string}):Promise<void>;clear():Promise<void>}>('SecureSession');
const speech=registerPlugin<{start():Promise<{text:string}>;stop():Promise<void>}>('AdexSpeech');
export const native=Capacitor.isNativePlatform();
if(native)document.documentElement.classList.add("native-app");
export async function loadSession(){return native?(await secure.get()).token:'';}
export async function saveSession(token:string){if(native)await secure.set({token});}
export async function clearSession(){if(native)await secure.clear();}
export async function photo(cameraOnly=false){const p=await Camera.getPhoto({source:cameraOnly?CameraSource.Camera:CameraSource.Photos,resultType:CameraResultType.Uri,quality:85});if(!p.webPath)throw new Error('PHOTO_UNAVAILABLE');const r=await fetch(p.webPath);if(!r.ok)throw new Error('PHOTO_UNAVAILABLE');const b=await r.blob();return new File([b],'photo.'+p.format,{type:b.type||'image/'+p.format});}
let browserSpeech:{stop():void}|undefined;
export async function transcribe(){
 if(native)return (await speech.start()).text;
 const ctor=(window as unknown as {SpeechRecognition?:new()=>any;webkitSpeechRecognition?:new()=>any}).SpeechRecognition||(window as unknown as {webkitSpeechRecognition?:new()=>any}).webkitSpeechRecognition;
 if(!ctor)throw new Error('此浏览器不支持语音识别，请使用 iOS 客户端。');
 return new Promise<string>((resolve,reject)=>{
  const recognizer=new ctor();browserSpeech=recognizer;let text='',settled=false;
  const timer=setTimeout(()=>recognizer.stop(),45000);
  const finish=(error?:Error)=>{if(settled)return;settled=true;clearTimeout(timer);browserSpeech=undefined;error?reject(error):resolve(text);};
  recognizer.lang='zh-CN';recognizer.interimResults=true;recognizer.continuous=true;
  recognizer.onresult=(event:any)=>{text=Array.from(event.results as any[]).map((result:any)=>result[0].transcript).join('');};
  recognizer.onerror=(event:any)=>finish(new Error(event.error==='not-allowed'?'MICROPHONE_PERMISSION_DENIED':'语音识别暂不可用，请重试'));
  recognizer.onend=()=>finish();
  try{recognizer.start();}catch(error){finish(error instanceof Error?error:new Error('语音识别无法启动'));}
 });
}
export async function stopSpeech(){if(native)await speech.stop();else browserSpeech?.stop();}


if(native){window.addEventListener("keyboardWillShow",()=>document.documentElement.classList.add("keyboard-open"));window.addEventListener("keyboardWillHide",()=>document.documentElement.classList.remove("keyboard-open"));}
