from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import json, time
app=FastAPI()
users={}
rooms={}
room_counter=0
HTML=f"""
<!DOCTYPE html><html><head><meta name=viewport content='width=device-width,initial-scale=1'><meta http-equiv='Cache-Control' content='no-cache'><title>LA JAULA v{int(time.time())}</title>
<style>body{{background:#0a0a12;color:#fff;text-align:center;font-family:sans-serif;padding:20px}}button{{background:#ff2a2a;border:0;color:#fff;padding:15px;border-radius:10px;width:90%;margin:8px;font-size:18px;font-weight:bold}}input{{padding:12px;border-radius:8px;border:0;width:80%;margin:5px;text-align:center}}#tap{{height:200px;font-size:40px;display:none;background:#00ff88;color:#000}}.room{{border:2px solid #ff2a2a;padding:12px;margin:10px;border-radius:10px;background:#1a1a2e}}</style>
</head><body><h1>🔥 LA JAULA 🔥</h1>
<div id=login><input id=name placeholder='Tu apodo'><button onclick=entrar()>ENTRAR 1000 MONEDAS</button><p id=coins></p></div>
<div id=lobby style=display:none>
<h2 style=color:#0f0>JAULAS ABIERTAS (toca UNIRSE):</h2>
<div id=roomsList style=background:#000;padding:10px;min-height:60px>Cargando...</div>
<button onclick=listar() style=background:#444>🔄 ACTUALIZAR LISTA</button>
<hr>
<input id=bet type=number value=100 min=100><button onclick=crear()>CREAR JAULA (100 a infinito)</button>
</div>
<div id=arena style=display:none><h2 id=vs></h2><h1 id=score>0-0</h1><button id=tapBtn ontouchstart=tap(event) onclick=tap(event) style=display:none>TAP!!!</button><h2 id=win></h2><button onclick=location.reload()>SALIR</button></div>
<script>
let user,ws,roomId;
async function entrar(){{user=document.getElementById('name').value.trim();if(!user)return alert('Pon apodo');let r=await fetch(`/user/${{user}}?t=${{Date.now()}}`);let d=await r.json();document.getElementById('coins').innerText=`Saldo: ${{d.coins}}`;document.getElementById('login').style.display='none';document.getElementById('lobby').style.display='block';listar();setInterval(listar,2000)}}
async function crear(){{let b=document.getElementById('bet').value;let r=await fetch(`/create/${{user}}/${{b}}`,{{method:'POST'}});let d=await r.json();if(d.error)return alert(d.error);unirse(d.room_id)}}
async function listar(){{try{{let r=await fetch('/rooms?t='+Date.now());let d=await r.json();let el=document.getElementById('roomsList');if(!d.rooms.length){{el.innerHTML='<b style=color:yellow>No hay jaulas, crea una!</b>';return}}let h='';d.rooms.forEach(rm=>{{h+=`<div class=room>JAULA #${{rm.id}} - ${{rm.bet}} monedas - Creador: ${{rm.owner}} <br><button onclick="unirse(${{rm.id}})">🔥 UNIRSE A ESTA</button></div>`}});el.innerHTML=h;}}catch(e){{document.getElementById('roomsList').innerHTML='Error cargando'}}}}
function unirse(id){{roomId=id;document.getElementById('lobby').style.display='none';document.getElementById('arena').style.display='block';document.getElementById('tapBtn').style.display='block';document.getElementById('vs').innerText=`JAULA #${{id}} - VS`;let p=location.protocol=='https:'?'wss:':'ws:';ws=new WebSocket(`${{p}}//${{location.host}}/ws/${{id}}/${{user}}`);ws.onmessage=e=>{{let data=JSON.parse(e.data);let pl=data.players;let t=data.taps;if(pl.length==2)document.getElementById('score').innerText=`${{pl[0]}} ${{t[pl[0]]||0}} - ${{t[pl[1]]||0}} ${{pl[1]}}`;else document.getElementById('score').innerText=`Esperando rival... ${{pl[0]}} en jaula`;if(data.winner){{document.getElementById('win').innerText=`GANADOR: ${{data.winner}}`;document.getElementById('tapBtn').style.display='none';setTimeout(()=>location.reload(),4000)}}}}}
function tap(e){{if(e)e.preventDefault();if(ws)ws.send('tap')}}
</script></body></html>
"""
@app.get("/")
def home(): return HTMLResponse(HTML)
@app.get("/user/{name}")
def get_user(name: str):
    if name not in users: users[name]=1000
    return {"coins": users[name]}
@app.get("/rooms")
def list_rooms():
    lista=[]
    for id,r in rooms.items():
        if len(r["players"])<2 and not r.get("finished"): lista.append({"id":id,"bet":r["bet"],"owner":r["players"][0] if r["players"] else "?"})
    return {"rooms": lista}
@app.post("/create/{user}/{bet}")
def create_room(user: str, bet: int):
    global room_counter
    if users.get(user,0)<bet: return {"error":"No tienes monedas"}
    users[user]-=bet
    room_counter+=1
    rooms[room_counter]={"bet":bet,"players":[user],"taps":{user:0},"conns":[],"pot":bet,"finished":False}
    return {"room_id":room_counter}
class ConnManager:
    async def connect(self,ws,room_id): await ws.accept(); rooms[room_id]["conns"].append(ws)
    def disconnect(self,ws,room_id):
        if ws in rooms[room_id]["conns"]: rooms[room_id]["conns"].remove(ws)
manager=ConnManager()
@app.websocket("/ws/{room_id}/{user}")
async def ws_endpoint(websocket: WebSocket, room_id: int, user: str):
    if room_id not in rooms: await websocket.close(); return
    room=rooms[room_id]
    if user not in room["players"]:
        if len(room["players"])>=2: await websocket.close(); return
        if users.get(user,0)<room["bet"]: await websocket.close(); return
        users[user]-=room["bet"]; room["players"].append(user); room["taps"][user]=0; room["pot"]+=room["bet"]
    await manager.connect(websocket,room_id)
    for conn in room["conns"]: await conn.send_text(json.dumps({"players":room["players"],"taps":room["taps"]}))
    try:
        while True:
            await websocket.receive_text()
            if room["finished"]: continue
            room["taps"][user]=room["taps"].get(user,0)+1
            if room["taps"][user]>=50:
                room["finished"]=True; users[user]+=room["pot"]
                for conn in room["conns"]: await conn.send_text(json.dumps({"players":room["players"],"taps":room["taps"],"winner":user}))
                break
            for conn in room["conns"]: await conn.send_text(json.dumps({"players":room["players"],"taps":room["taps"]}))
    except WebSocketDisconnect: manager.disconnect(websocket,room_id)
