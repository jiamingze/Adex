import {useEffect,useRef,useState} from 'react';
import {Plus,Image,Camera,FileUp,X,LoaderCircle} from 'lucide-react';
import {native,photo} from './platform';

export function AttachmentMenu({guest,onSignIn,onFile}:{guest:boolean;onSignIn:()=>void;onFile:(file:File,key:string)=>Promise<void>}){
 const [open,setOpen]=useState(false),[uploading,setUploading]=useState(false),[error,setError]=useState('');
 const pending=useRef<{file:File;key:string}|null>(null);
 const input=useRef<HTMLInputElement>(null),close=useRef<HTMLButtonElement>(null),trigger=useRef<HTMLButtonElement>(null);
 useEffect(()=>{if(!open)return;close.current?.focus();const handler=(e:KeyboardEvent)=>{if(e.key==='Escape'){setOpen(false);trigger.current?.focus();}};window.addEventListener('keydown',handler);return()=>window.removeEventListener('keydown',handler);},[open]);
 async function upload(file:File){if(uploading)return;if(pending.current?.file!==file)pending.current={file,key:crypto.randomUUID()};setUploading(true);setError('');try{await onFile(file,pending.current!.key);pending.current=null;setOpen(false);}catch(e){setError(e instanceof Error?e.message:'上传失败，请重试');}finally{setUploading(false);}}
 function pick(accept:string){if(input.current){input.current.accept=accept;input.current.click();}}
 return <>
  <button ref={trigger} type="button" className="composer-add" aria-label="添加照片或文件" disabled={uploading} onClick={()=>{if(guest){onSignIn();return;}(document.activeElement as HTMLElement)?.blur();setError('');setOpen(true);}}>{uploading?<LoaderCircle className="voice-spinner" size={20}/>:<Plus size={22}/>}</button>
  <input ref={input} type="file" hidden onChange={e=>{const file=e.target.files?.[0];e.target.value='';if(file)void upload(file);}}/>
  {open&&<div className="attachment-backdrop" onClick={e=>{if(e.target===e.currentTarget&&!uploading)setOpen(false);}}>
   <section className="attachment-sheet" role="dialog" aria-modal="true" aria-label="添加到对话">
    <div className="sheet-handle"/><header><h2>添加到对话</h2><button ref={close} className="icon-button" aria-label="关闭附件菜单" disabled={uploading} onClick={()=>{setOpen(false);trigger.current?.focus();}}><X size={20}/></button></header>
    <button disabled={uploading} onClick={async()=>{if(!native){pick('image/*');return;}setError('');try{await upload(await photo());}catch(e){if(!/cancel/i.test(String(e)))setError('无法读取照片，请检查相册权限后重试');}}}><Image size={23}/><span>照片图库<small>从相册添加图片</small></span></button>
    {native&&<button disabled={uploading} onClick={async()=>{setError('');try{await upload(await photo(true));}catch{setError('未选择照片，或相机权限未开启');}}}><Camera size={23}/><span>拍照<small>拍摄后添加到对话</small></span></button>}
    <button disabled={uploading} onClick={()=>pick('')}><FileUp size={23}/><span>选择文件<small>文档、音频或其他附件</small></span></button>
    {uploading&&<p role="status">正在上传…</p>}{error&&<div role="alert" className="form-error">{error}{pending.current&&<button className="text-button" disabled={uploading} onClick={()=>void upload(pending.current!.file)}>重新上传</button>}</div>}
   </section>
  </div>}
 </>;
}
