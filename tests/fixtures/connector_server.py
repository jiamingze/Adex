"""Loopback TEST_FIXTURE Google/APNs emulator, never a real external execution."""
import base64
import json
from email import message_from_bytes
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from uuid import uuid4

STATE = {"events": [], "messages": [], "pushes": [], "codes": {}, "fault": "", "writes": 0}

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def reply(self, body, status=200):
        raw=json.dumps(body).encode(); self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    def do_GET(self):
        path=urlparse(self.path).path;q=parse_qs(urlparse(self.path).query)
        if path=='/fixture/state':return self.reply({k:v for k,v in STATE.items() if k!='codes'})
        if path=='/oauth/authorize':
            code=uuid4().hex;STATE['codes'][code]={'scope':q['scope'][0],'challenge':q['code_challenge'][0]};return self.reply({'code':code,'state':q['state'][0],'provider':'TEST_FIXTURE'})
        if path=='/calendar/calendars/primary/events':return self.reply({'items':STATE['events']})
        if path.startswith('/calendar/calendars/primary/events/'):
            event=next((e for e in STATE['events'] if e['id']==path.rsplit('/',1)[1]),None);return self.reply(event or {},200 if event else 404)
        if path=='/gmail/users/me/messages':
            values=STATE['messages'];query=q.get('q',[''])[0]
            if 'rfc822msgid:' in query:
                target=query.split('rfc822msgid:')[1];values=[m for m in values if any(h['name'].lower()=='message-id' and h['value'].strip('<>')==target for h in m.get('payload',{}).get('headers',[]))]
            return self.reply({'messages':[{'id':m['id']} for m in values]})
        if path.startswith('/gmail/users/me/messages/'):
            value=next((m for m in STATE['messages'] if m['id']==path.rsplit('/',1)[1]),None);return self.reply(value or {},200 if value else 404)
        return self.reply({},404)
    def body(self):
        raw=self.rfile.read(int(self.headers.get('Content-Length','0')))
        return parse_qs(raw.decode()) if 'application/x-www-form-urlencoded' in self.headers.get('Content-Type','') else json.loads(raw or b'{}')
    def do_POST(self):
        path=urlparse(self.path).path;data=self.body()
        if path=='/fixture/seed':
            STATE.update(data);return self.reply({'provider':'TEST_FIXTURE'})
        if path=='/oauth/token':
            if data.get('grant_type',[''])[0]=='refresh_token':return self.reply({'access_token':'test-access','expires_in':3600})
            saved=STATE['codes'].pop(data.get('code',[''])[0],None)
            import hashlib
            challenge=base64.urlsafe_b64encode(hashlib.sha256(data.get('code_verifier',[''])[0].encode()).digest()).decode().rstrip('=')
            if not saved or saved['challenge']!=challenge:return self.reply({'error':'invalid_grant'},400)
            return self.reply({'access_token':'test-access','refresh_token':'test-refresh','expires_in':3600,'scope':saved['scope']})
        if path=='/oauth/revoke':return self.reply({})
        if path=='/gmail/users/me/messages/send':
            email=message_from_bytes(base64.urlsafe_b64decode(data['raw']));mid=uuid4().hex
            STATE['writes']+=1;STATE['messages'].append({'id':mid,'threadId':mid,'historyId':'1','labelIds':['SENT'],'payload':{'headers':[{'name':'Message-ID','value':email['Message-ID']}]}})
            return self.reply({'id':mid},503 if STATE['fault']=='gmail_unknown' else 200)
        if path.startswith('/apns/3/device/'):
            STATE['pushes'].append({'payload':data,'provider':'TEST_FIXTURE','apns_id':self.headers.get('apns-id')});return self.reply({})
        return self.reply({},404)
    def do_PATCH(self):
        path=urlparse(self.path).path;data=self.body()
        if path.startswith('/calendar/calendars/primary/events/'):
            event=next((e for e in STATE['events'] if e['id']==path.rsplit('/',1)[1]),None)
            if not event:return self.reply({},404)
            if self.headers.get('If-Match')!=event['etag']:return self.reply({},412)
            event.update(data);event['etag']=uuid4().hex;STATE['writes']+=1;return self.reply(event)
        return self.reply({},404)

if __name__=='__main__':ThreadingHTTPServer(('127.0.0.1',18109),Handler).serve_forever()
