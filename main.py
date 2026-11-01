
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
import json, uuid
app=FastAPI()
users,rooms={}, {}
@app.get("/", response_class=HTMLResponse)
def home(): return open("index.html").read()
@app.get("/user/{name}")
def get_user(name: str):
    if name not in users: users[name]=1000
    return {"coins": users[name]}
@app.post("/create/{name}/{bet}")
def create_room(name: str, bet: int):
    if bet<100: return {"error":"Minimo 100"}
    if users.get(name,0)<bet: return {"error":"Sin saldo"}
    rid=str(uuid.uuid4())[:6]
    rooms[rid]={"bet":bet,"players":[name],"taps":{name:0},"winner":None}
    users[name]-=bet
    return {"room_id":rid}
@app.websocket("/ws/{room_id}/{name}")
async def ws(websocket: WebSocket, room_id: str, name: str):
    await websocket.accept()
    r=rooms.get(room_id)
    if not r: return
    if name not in r["players"]:
        if len(r["players"])>=2: return
        if users[name]<r["bet"]: return
        r["players"].append(name); r["taps"][name]=0; users[name]-=r["bet"]
    try:
        while True:
            await websocket.receive_text()
            r["taps"][name]+=1
            if r["taps"][name]>=50 and not r["winner"]:
                r["winner"]=name; users[name]+=int(r["bet"]*2*0.9)
            await websocket.send_text(json.dumps(r))
    except: pass
