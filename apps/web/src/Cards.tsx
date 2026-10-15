import {useEffect,useState} from 'react';
import {workspaceApi,api} from './api';
import type {MusicTrack} from './api';
export type Card={schema_version:number;type:string;card_id:string;conversation_id:string;message_id:string;actions:string[];data?:Record<string,unknown>};
function go(page:string){window.dispatchEvent(new CustomEvent('adex:navigate',{detail:page}));}
function sourceList(card:Card){
 const items=Array.isArray(card.data?.items)?card.data.items as {title?:string;url?:string;snippet?:string}[]:[];
 return <details className="source-card">
  <summary><span>来源与证据</span><span className="source-count">{items.length} 个来源</span></summary>
  <ol className="source-items">{items.map((item,index)=><li key={index}>
   {item.url&&/^https?:\/\//.test(item.url)?<a href={item.url} target="_blank" rel="noopener noreferrer">{item.title||item.url}</a>:<span>{item.title||`来源 ${index+1}`}</span>}
   {item.snippet&&<p>{item.snippet.slice(0,160)}</p>}
  </li>)}</ol>
  <small className="source-time">抓取时间：{String(card.data?.fetched_at||'见来源内容')}</small>
 </details>;
}
function workspaceCard(card:Card){return <section className="workspace-card"><strong>{String(card.data?.title||'作品已保存')}</strong><small>{String(card.data?.kind||'')}</small><button className="button" onClick={()=>go('workspace')}>查看作品与版本</button></section>;}
function GeneratedAudio({card}:{card:Card}){const [url,setUrl]=useState(''),[error,setError]=useState('');useEffect(()=>{let live=true;const id=String(card.data?.file_id||'');if(id)workspaceApi.playback(id).then(value=>{if(live)setUrl(value);}).catch(()=>{if(live)setError('音频暂不可用，请到作品空间重试');});return()=>{live=false;};},[card.card_id]);return <section className="workspace-card"><strong>{card.data?.mock?'测试音频样例':'原创音乐'}</strong><small>{String(card.data?.model_id||'')} {card.data?.mock?'· 非真实歌曲生成':''}</small>{url?<><audio controls preload="metadata" src={url} onError={()=>setError('播放连接已失效，请重新加载音频')}/><p><a href={url} download="original-music.mp3">下载音频</a></p></>:<p>{error||'正在加载音频…'}</p>}{error&&url&&<p role="alert">{error} <button className="text-button" onClick={async()=>{try{setUrl(await workspaceApi.playback(String(card.data?.file_id)));setError('');}catch{setError('音频加载失败，请检查连接后重试');}}}>重新加载</button></p>}<button className="button" onClick={()=>go('workspace')}>查看作品与版本</button></section>;}
function GeneratedImage({card}:{card:Card}){
 const [url,setUrl]=useState(''),[error,setError]=useState('');
 useEffect(()=>{let live=true;let objectUrl='';workspaceApi.blob(String(card.data?.file_id||'')).then(blob=>{if(live){objectUrl=URL.createObjectURL(blob);setUrl(objectUrl);}}).catch(()=>{if(live)setError('图片加载失败，请在作品空间重试');});return()=>{live=false;if(objectUrl)URL.revokeObjectURL(objectUrl);};},[card.card_id]);
 return <section className="workspace-card"><strong>{card.data?.mock?'测试图片样例':'生成图片'}</strong>{url?<><img src={url} alt="根据你的请求生成的图片" loading="lazy" style={{width:'100%',maxHeight:420,objectFit:'contain',borderRadius:12}}/><a href={url} download="generated-image.png">下载图片</a></>:<p>{error||'正在加载图片…'}</p>}<button className="button" onClick={()=>go('workspace')}>查看作品与版本</button></section>;
}
function GeneratedVideo({card}:{card:Card}){
 const [url,setUrl]=useState(''),[poster,setPoster]=useState(''),[error,setError]=useState('');
 useEffect(()=>{let live=true;const id=String(card.data?.file_id||'');if(id)workspaceApi.playback(id).then(value=>{if(live)setUrl(value);}).catch(()=>{if(live)setError('视频暂不可用，请到作品空间重试');});const pid=card.data?.poster_file_id;if(pid)workspaceApi.playback(String(pid)).then(value=>{if(live)setPoster(value);}).catch(()=>{});return()=>{live=false;};},[card.card_id]);
 return <section className="workspace-card"><strong>{card.data?.mock?'测试视频样例':'生成视频'}</strong><small>{String(card.data?.model_id||'')}</small>{url?<><video controls playsInline preload="metadata" src={url} poster={poster||undefined} style={{width:'100%',maxHeight:420,borderRadius:12}}/><p><a href={url} download="generated-video.mp4">下载视频</a></p></>:<p>{error||'正在加载视频…'}</p>}<button className="button" onClick={()=>go('workspace')}>查看作品与版本</button></section>;
}
function TaskStatus({card}:{card:Card}){
 const [status,setStatus]=useState(String(card.data?.status||'QUEUED')),[error,setError]=useState('');
 useEffect(()=>{let live=true;let timer:ReturnType<typeof setTimeout>;const refresh=async()=>{try{const result=await api.runs();const run=result.items.find(r=>r.id===card.data?.run_id);if(live&&run){setStatus(run.status);setError(run.error_code||'');if(['COMPLETED','SUCCEEDED','FAILED','CANCELLED'].includes(run.status))return;}}catch{}if(live)timer=setTimeout(refresh,5000);};refresh();return()=>{live=false;clearTimeout(timer);};},[card.card_id]);
 const labels:Record<string,string>={QUEUED:'等待处理',WAITING_INPUT:'等待你接管或确认',RUNNING:'正在生成',COMPLETED:'已完成',SUCCEEDED:'已完成',FAILED:'生成失败',CANCELLED:'已取消'};
 const errors:Record<string,string>={MEDIA_PROVIDER_ACCESS_DENIED:'生成模型拒绝访问，请检查供应商权限或余额。',MUSIC_DAILY_LIMIT:'今日媒体生成额度已用完，请稍后重试。',MEDIA_PROVIDER_REJECTED:'供应商未接受本次生成请求。',PROVIDER_UNKNOWN:'供应商结果待核对，请查看运行状态。',STALE_EXECUTION:'本次执行已中断，请查看运行记录。'};
 return <section className="workspace-card"><strong>{card.data?.kind==='BROWSER'?'网页操作':card.data?.kind==='AUDIO'?'音乐创作':card.data?.kind==='IMAGE'?'图片生成':card.data?.kind==='VIDEO'?'视频生成':'后台任务'}</strong><small>{labels[status]||status}</small>{error&&<p role="alert">{errors[error]||`本次生成未完成（${error}）。请查看运行状态。`}</p>}<button className="button" onClick={()=>go(card.data?.kind==='BROWSER'?'browser':'tasks')}>{card.data?.kind==='BROWSER'?'打开浏览器面板':'查看运行状态'}</button></section>;
}
const registry:Record<string,(card:Card)=>React.ReactNode>={
 music_playlist:(card)=><div className="workspace-grid">{((card.data?.items||[]) as MusicTrack[]).map(track=><article className="workspace-card" key={track.track_id}><strong>{track.title}</strong>{track.artwork_url&&/^https:\/\/[^/]+\.mzstatic\.com\//.test(track.artwork_url)&&<img loading="lazy" src={track.artwork_url} alt={track.title+' 专辑封面'} width={100} height={100}/>}<small>{track.artists.join('、')} · {track.album}</small>{/^https:\/\/(music\.apple\.com|itunes\.apple\.com)\//.test(track.source_url)&&<a href={track.source_url} target="_blank" rel="noopener noreferrer">在官方平台打开 ↗</a>}</article>)}<small>目录查询时间：{String(card.data?.fetched_at||'')}</small></div>,
 source_list:sourceList,hotel_list:sourceList,poi_list:sourceList,
 artifact_preview:workspaceCard,trip_itinerary:workspaceCard,diagram_editor:workspaceCard,image_gallery:(card)=><GeneratedImage card={card}/>,generated_audio_player:(card)=><GeneratedAudio card={card}/>,generated_video_player:(card)=><GeneratedVideo card={card}/>,
 automation_status:(card)=><section className="workspace-card"><strong>定时任务已启用</strong><small>每天 {String(card.data?.local_time)} · {String(card.data?.timezone)}</small><button className="button" onClick={()=>go('tasks')}>管理定时任务</button></section>,
 task_status:(card)=><TaskStatus card={card}/>,
 media_generation_progress:(card)=><section className="workspace-card"><strong>创作任务</strong><small>{String(card.data?.status||'')}</small><button className="button" onClick={()=>go('tasks')}>查看进度与取消</button></section>,
 music_player:()=> <button className="button" onClick={()=>go('workspace')}>打开我的音频播放列表</button>,
 approval_request:()=> <button className="button" onClick={()=>go('tools')}>查看并批准操作草稿</button>,
 error_notice:(card)=><p role="alert">{String(card.data?.message||'当前操作未完成，请查看任务详情。')}</p>,
};
export function Cards({cards}:{cards:Card[]}){return <>{cards.map(card=><section key={card.card_id}>{card.schema_version===1&&registry[card.type]?registry[card.type](card):<small>此卡片版本暂不支持，请查看文字内容。</small>}</section>)}</>;}
