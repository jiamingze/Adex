package io.adex.app;
import io.adex.kernel.Kernel;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component
public class FileReconciler {
 final Kernel k; final FileApi files;
 public FileReconciler(Kernel k,FileApi files){this.k=k;this.files=files;}
 @Scheduled(fixedDelay=60000) public void reconcile(){
  // Grace period prevents interfering with a still-live upload.
  for(var row:k.db.queryForList("SELECT * FROM files WHERE status='PENDING' AND created_at<now()-interval '1 hour' LIMIT 100")){
   try{Path p=files.object((UUID)row.get("object_id"));if(Files.isRegularFile(p,LinkOption.NOFOLLOW_LINKS)){
    var hash=MessageDigest.getInstance("SHA-256");try(var in=Files.newInputStream(p)){byte[] b=new byte[65536];int n;while((n=in.read(b))!=-1)hash.update(b,0,n);}
    if(HexFormat.of().formatHex(hash.digest()).equals(row.get("sha256"))&&Files.size(p)==((Number)row.get("size_bytes")).longValue()){
     k.db.update("UPDATE files SET status='READY' WHERE id=? AND status='PENDING'",row.get("id"));continue;}
   }
   k.db.update("UPDATE files SET status='DELETED',deleted_at=now() WHERE id=? AND status='PENDING'",row.get("id"));
   }catch(Exception ignored){/* Retry reconciliation; never expose a partially verified object. */}
  }
  try(var shards=Files.list(files.root)){
   for(Path shard:shards.toList()){if(Files.isSymbolicLink(shard)||!Files.isDirectory(shard))continue;
    try(var objects=Files.list(shard)){for(Path p:objects.toList()){
     if(Files.isSymbolicLink(p)||Files.getLastModifiedTime(p).toMillis()>System.currentTimeMillis()-86400000L)continue;
     String name=p.getFileName().toString();UUID id;try{id=UUID.fromString(name.endsWith(".tmp")?name.substring(0,name.length()-4):name);}catch(Exception e){continue;}
     var rows=k.db.queryForList("SELECT status,deleted_at FROM files WHERE object_id=?",id);
     if(rows.isEmpty()||("DELETED".equals(rows.getFirst().get("status")) && rows.getFirst().get("deleted_at") instanceof java.sql.Timestamp deleted && deleted.getTime()<System.currentTimeMillis()-86400000L))Files.deleteIfExists(p);
    }}
   }
  }catch(Exception ignored){/* PostgreSQL outage must never authorize deletion. */}
 }
}
