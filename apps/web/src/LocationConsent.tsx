import { useState } from "react";
import { MapPin } from "lucide-react";
import { saveLocationPreference, type LocationMode } from "./locationContext";
export function LocationConsent({onChoose}:{onChoose:(mode:LocationMode)=>void}){
 const [city,setCity]=useState("");
 function choose(mode:LocationMode){saveLocationPreference(mode,city);onChoose(mode);}
 return <div className="modal-backdrop"><section className="modal" role="dialog" aria-modal="true" aria-labelledby="location-title">
  <MapPin size={24}/><h2 id="location-title">让回答更贴近你</h2>
  <p>查询天气和附近地点时，使用近似位置。位置会发送给 Adex 和相关查询服务，不会后台追踪或自动存入长期记忆。</p>
  <button className="primary" onClick={()=>choose("device")}>使用当前位置</button>
  <label>也可以手动选择城市或区域<input aria-label="城市或区域" value={city} maxLength={120} onChange={e=>setCity(e.target.value)} placeholder="例如：上海市徐汇区"/></label>
  <div className="modal-actions"><button disabled={!city.trim()} onClick={()=>choose("manual")}>使用此城市</button><button onClick={()=>choose("off")}>暂不使用位置</button></div>
 </section></div>;
}
