import {useEffect,useRef,useState} from 'react';
import {Markdown} from './Markdown';

// Reveal buffered network frames gradually without changing the committed answer.
export function LiveResponse({content}:{content:string}){
 const target=useRef(content),shown=useRef('');const [text,setText]=useState('');
 useEffect(()=>{target.current=content;if(!content.startsWith(shown.current)){shown.current='';setText('');}},[content]);
 useEffect(()=>{const timer=setInterval(()=>{const remaining=target.current.length-shown.current.length;if(remaining>0){shown.current=target.current.slice(0,shown.current.length+Math.max(2,Math.ceil(remaining/12)));setText(shown.current);}},32);return()=>clearInterval(timer);},[]);
 return <div className="live-response"><Markdown content={text}/><span className="stream-cursor" aria-hidden="true"/></div>;
}
