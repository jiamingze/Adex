export type Preferences={theme:'system'|'light'|'dark';enterSend:boolean;defaultSearch:boolean};
export function preferences():Preferences{try{return {theme:'system',enterSend:true,defaultSearch:false,...JSON.parse(localStorage.getItem('adex.preferences')||'{}')};}catch{return {theme:'system',enterSend:true,defaultSearch:false};}}
export function applyPreferences(value:Preferences){localStorage.setItem('adex.preferences',JSON.stringify(value));document.documentElement.dataset.theme=value.theme;window.dispatchEvent(new CustomEvent('adex:preferences',{detail:value}));}
document.documentElement.dataset.theme=preferences().theme;
