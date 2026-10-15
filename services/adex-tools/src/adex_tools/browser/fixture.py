"""TEST_FIXTURE HTML only. Selected by trusted parent exclusively in adex_test_* DBs.

Not a real third-party service, publication, order or payment. No external writes.
"""

HTML = """<!doctype html><html><head><meta charset="utf-8"><title>TEST_FIXTURE Browser Lab</title></head><body>
<h1>TEST_FIXTURE 本地浏览器演练</h1><p>这是隔离测试页面，不是真实发布或购物。</p>
<label>标题<input id="title"></label><label>正文<textarea id="body"></textarea></label>
<label>密码<input id="password" type="password"></label>
<button id="publish">发布</button><div id="receipt" role="status"></div>
<script>document.querySelector('#publish').onclick=async()=>{
 const result=await fetch('/publish',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title:document.querySelector('#title').value,content:document.querySelector('#body').value})});
 const data=await result.json();document.querySelector('#receipt').textContent='TEST_FIXTURE 发布成功 笔记ID：'+data.note_id;
};</script></body></html>"""
