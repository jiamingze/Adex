import { registerPlugin } from "@capacitor/core";
import { native } from "./platform";
import { freshLocation, type ClientLocation, type LocationMode } from "./locationModel";
export { locationRelevant, type ClientLocation, type LocationMode } from "./locationModel";
const plugin = registerPlugin<{current():Promise<Omit<ClientLocation,"source">>}>("AdexLocation");
let cached:ClientLocation|undefined;
export function locationPreference(){return {mode:localStorage.getItem("adex.location.mode") as LocationMode|null,city:localStorage.getItem("adex.location.city")||""};}
export function saveLocationPreference(mode:LocationMode,city="") {cached=undefined;localStorage.setItem("adex.location.mode",mode);localStorage.setItem("adex.location.city",city.trim().slice(0,120));}
window.addEventListener("adex:session-changed",()=>{cached=undefined;});
export async function currentLocation():Promise<ClientLocation|undefined>{
 const {mode,city}=locationPreference();
 if(mode==="manual")return city?{source:"manual",label:city,observed_at:new Date().toISOString()}:undefined;
 if(mode!=="device")return undefined;
 if(cached&&freshLocation(cached))return cached;
 try{
  const fix=native?await plugin.current():await new Promise<Omit<ClientLocation,"source">>((resolve,reject)=>{
   if(!navigator.geolocation){reject(new Error("LOCATION_UNAVAILABLE"));return;}
   navigator.geolocation.getCurrentPosition(p=>resolve({latitude:Math.round(p.coords.latitude*100)/100,longitude:Math.round(p.coords.longitude*100)/100,label:"",observed_at:new Date(p.timestamp).toISOString()}),reject,{enableHighAccuracy:false,timeout:10000,maximumAge:300000});
  });
  const result:ClientLocation={...fix,source:"device"};
  if(locationPreference().mode!=="device"||!freshLocation(result))return undefined;
  return cached=result;
 }catch{return undefined;}
}
