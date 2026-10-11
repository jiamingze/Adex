package io.adex.app;
import io.adex.kernel.Kernel;
import jakarta.servlet.http.HttpServletRequest;
import java.util.*;
import org.springframework.web.bind.annotation.*;
@RestController
public class AccountApi {
 final Kernel k;final Auth auth; final ChatStore chat; final MemoryService memory;
 public AccountApi(Kernel k,Auth auth,ChatStore chat,MemoryService memory){this.k=k;this.auth=auth;this.chat=chat;this.memory=memory;}
 @GetMapping("/api/v1/settings")public Object settings(HttpServletRequest r){return k.row("SELECT username,settings FROM users WHERE id=?",auth.owner(r));}
 @PatchMapping("/api/v1/settings")public Object save(HttpServletRequest r,@RequestBody Map<String,Object>b){
  for(String key:b.keySet())if(!Set.of("memory_enabled","email_notifications","email").contains(key))throw Kernel.error(400,"INVALID_SETTING");
  for(String key:List.of("memory_enabled","email_notifications"))if(b.containsKey(key)&&!(b.get(key) instanceof Boolean))throw Kernel.error(400,"INVALID_SETTING");
  if(b.containsKey("email")&&!(b.get("email") instanceof String))throw Kernel.error(400,"INVALID_EMAIL");
  if(b.containsKey("email")&&!String.valueOf(b.get("email")).isEmpty()&&!String.valueOf(b.get("email")).matches("[^\\s@]{1,80}@[^\\s@]{1,120}\\.[^\\s@]{2,20}"))throw Kernel.error(400,"INVALID_EMAIL");
  return k.row("UPDATE users SET settings=settings||?::jsonb WHERE id=? RETURNING settings",k.encode(b),auth.owner(r));
 }
 @GetMapping("/api/v1/usage")public Object usage(HttpServletRequest r){UUID owner=auth.owner(r);var result=new LinkedHashMap<String,Object>();result.put("storage",k.row("SELECT COALESCE(sum(size_bytes),0) AS used_bytes,262144000 AS quota_bytes FROM files WHERE owner_id=? AND status<>'DELETED'",owner));
  for(String service:List.of("agent","tools")){try{result.put(service.equals("agent")?"model":"tools",k.call(service,"usage:read",owner,null,"GET","/internal/usage",null));}catch(Exception e){result.put(service.equals("agent")?"model":"tools",Map.of("status","UNAVAILABLE"));}}return result;
 }
 @PostMapping("/api/v1/security/revoke-sessions")public Object revoke(HttpServletRequest r){String current=Kernel.hash(auth.sessionToken(r));k.db.update("DELETE FROM sessions WHERE owner_id=? AND token_hash<>?",auth.owner(r),current);return Map.of("ok",true);}
 @PatchMapping("/api/v1/conversations/{id}")public Object rename(HttpServletRequest r,@PathVariable UUID id,@RequestBody Map<String,Object>b){chat.own(auth.owner(r),id);return k.row("UPDATE conversations SET title=? WHERE id=? RETURNING *",Kernel.text(b,"title",200),id);}
 @DeleteMapping("/api/v1/conversations/{id}")public Object delete(HttpServletRequest r,@PathVariable UUID id){
  UUID owner=auth.owner(r);
  return k.tx.execute(s->{
   k.row("SELECT id FROM users WHERE id=? FOR UPDATE",owner);
   chat.own(owner,id);k.row("SELECT id FROM conversations WHERE id=? FOR UPDATE",id);
   for(var m:k.db.queryForList("SELECT id FROM memories WHERE owner_id=? AND deleted_at IS NULL AND EXISTS (SELECT 1 FROM messages WHERE conversation_id=? AND jsonb_exists(source_refs,messages.id::text))",owner,id))memory.remove(owner,(UUID)m.get("id"));
   k.db.update("DELETE FROM summaries WHERE conversation_id=?",id);
   k.db.update("UPDATE users SET memory_revision=memory_revision+1 WHERE id=?",owner);
   k.db.update("UPDATE turns SET status='CANCELLED',epoch=epoch+1,lease_until=NULL WHERE conversation_id=? AND status IN ('QUEUED','RUNNING')",id);
   k.db.update("UPDATE conversations SET deleted_at=now() WHERE id=?",id);
   return Map.of("ok",true);
  });
 }
 @PostMapping("/api/v1/conversations/{id}/stop")public Object stop(HttpServletRequest r,@PathVariable UUID id){return k.tx.execute(s->{chat.own(auth.owner(r),id);k.row("SELECT id FROM conversations WHERE id=? FOR UPDATE",id);k.db.update("UPDATE turns SET status='CANCELLED',epoch=epoch+1,lease_until=NULL WHERE conversation_id=? AND status IN ('QUEUED','RUNNING')",id);chat.event(id,"turn.cancelled",Map.of());return Map.of("ok",true);});}
 @GetMapping("/api/v1/search")public Object search(HttpServletRequest r,@RequestParam String q){if(q.isBlank()||q.length()>200)throw Kernel.error(400,"INVALID_QUERY");return Kernel.items(k.db.queryForList("SELECT m.id,m.conversation_id,m.content,c.title FROM messages m JOIN conversations c ON c.id=m.conversation_id WHERE c.owner_id=? AND c.deleted_at IS NULL AND (to_tsvector('simple',m.content)@@plainto_tsquery('simple',?) OR m.content ILIKE ?) ORDER BY m.created_at DESC LIMIT 50",auth.owner(r),q,"%"+q+"%"));}
}
