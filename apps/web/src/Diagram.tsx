import {useEffect,useState} from 'react';
import DOMPurify from 'dompurify';
import {workspaceApi} from './api';
import {Button} from '@adex/ui-web';

export function Diagram({source,artifactId,versionId,canExport}:{source:string;artifactId:string;versionId:string;canExport:boolean}){
 const [svg,setSvg]=useState(''),[error,setError]=useState('');
 useEffect(()=>{let alive=true;setError('');setSvg('');const timer=setTimeout(async()=>{try{
  if(source.length>20000||!/^\s*(flowchart|graph|sequenceDiagram|classDiagram)\b/.test(source)||/%%\{|<|>|\bclick\b|https?:|javascript:|\bstyle\b|\bclassDef\b/i.test(source.replace(/-->|->>|-->>/g,'')))throw new Error('图源码包含不支持的指令，请使用标准节点和连线。');
  const mermaid=(await import('mermaid')).default;
  mermaid.initialize({startOnLoad:false,securityLevel:'strict',maxTextSize:20000,maxEdges:100,htmlLabels:false,theme:'default',flowchart:{htmlLabels:false},suppressErrorRendering:true});
  await mermaid.parse(source);
  const result=await mermaid.render('diagram'+crypto.randomUUID().replace(/-/g,''),source);
  const clean=DOMPurify.sanitize(result.svg,{USE_PROFILES:{svg:true,svgFilters:true},FORBID_TAGS:['foreignObject','script','a','image','animate','set','animateTransform','animateMotion','mpath'],FORBID_ATTR:['href','xlink:href']});
  if(alive)setSvg(clean);
 }catch(e){if(alive)setError(String(e));}},300);return()=>{alive=false;clearTimeout(timer);};},[source]);
 async function download(data:Blob,name:string){if(!canExport){setError("请先保存图源码，再导出对应版本。");return;}try{const bytes=await data.arrayBuffer();const sha=Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256",bytes))).map(b=>b.toString(16).padStart(2,"0")).join("");const file=await workspaceApi.upload(new File([data],name,{type:data.type}),"export:"+versionId+":"+sha.substring(0,24));await workspaceApi.registerExport(artifactId,versionId,file.id,name.endsWith("svg")?"SVG":"PNG");}catch(e){setError("导出文件保存失败："+String(e));return;}const url=URL.createObjectURL(data);const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
 async function png(){const image=new Image();const url=URL.createObjectURL(new Blob([svg],{type:'image/svg+xml'}));image.onload=()=>{const canvas=document.createElement('canvas');canvas.width=Math.min(image.width||1200,3000);canvas.height=Math.min(image.height||800,3000);const ctx=canvas.getContext('2d')!;ctx.fillStyle='#ffffff';ctx.fillRect(0,0,canvas.width,canvas.height);ctx.drawImage(image,0,0,canvas.width,canvas.height);canvas.toBlob(b=>{if(b)download(b,'diagram.png');});URL.revokeObjectURL(url);};image.onerror=()=>{setError('PNG 导出失败，请下载 SVG。');URL.revokeObjectURL(url);};image.src=url;}
 return <div>{error?<p role="alert">{error}</p>:svg?<><iframe title="架构图预览" sandbox="" srcDoc={'<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'">'+svg} style={{width:'100%',height:500,border:0}}/><Button disabled={!canExport} onClick={()=>download(new Blob([svg],{type:'image/svg+xml'}),'diagram.svg')}>导出 SVG</Button><Button disabled={!canExport} onClick={png}>导出 PNG</Button></>:<p>正在校验和渲染图形…</p>}</div>;
}
