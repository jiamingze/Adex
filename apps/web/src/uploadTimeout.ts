export function uploadDeadline<T>(work:Promise<T>,milliseconds=45000):Promise<T>{
 return new Promise((resolve,reject)=>{
  const timer=setTimeout(()=>reject(new Error('上传超时，请检查网络后重试')),milliseconds);
  work.then(value=>{clearTimeout(timer);resolve(value);},error=>{clearTimeout(timer);reject(error);});
 });
}
