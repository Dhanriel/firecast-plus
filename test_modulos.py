"""Roda os modulos do plugin na lua54 do Firecast com o SDK simulado: executa os asserts de cada arquivo."""
import ctypes, os, sys

lua = ctypes.CDLL(os.path.join(os.environ["LOCALAPPDATA"], "Firecast", "lua54x64.dll"))
lua.luaL_newstate.restype = ctypes.c_void_p
for f, a in [("luaL_openlibs", [ctypes.c_void_p]),
             ("luaL_loadbufferx", [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t, ctypes.c_char_p, ctypes.c_char_p]),
             ("lua_pcallk", [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_ssize_t, ctypes.c_void_p]),
             ("lua_tolstring", [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p])]:
    getattr(lua, f).argtypes = a
lua.lua_tolstring.restype = ctypes.c_char_p

STUB = b"""
NDB = {load = function() return {} end}
Firecast = {Messaging = {listen = function() end}}
Internet = {httpEncode = function(s) return s end}
local real = require
require = function(n) if n == "ui.dlua" then return {novo = function() end} end return {} end
"""
for nome in ("previa.dlua", "turno.dlua"):
    L = lua.luaL_newstate()
    lua.luaL_openlibs(L)
    src = STUB + open("plugin/" + nome, "rb").read()
    r = lua.luaL_loadbufferx(L, src, len(src), ("@" + nome).encode(), b"t") or lua.lua_pcallk(L, 0, 0, 0, 0, None)
    if r != 0:
        sys.exit("FALHOU: " + lua.lua_tolstring(L, -1, None).decode("utf-8", "replace"))
    print("ok", nome)

# ui.escrever com o arquivo preso (ajudante ou antivirus lendo, como no PC de um jogador): devolve false, sem erro
TESTE_UI = b"""
local preso = false
VHD = {fileExists = function() return true end,
       deleteFile = function() if preso then error("Acesso negado [piscar.txt]") end end,
       openFile = function() return {write = function() end, close = function() end} end}
require = function(n) if n == "utils.lua" then return {binaryEncode = function(b, _, t) return #t end} end return {} end
local ui = load(UI_SRC, "@ui.dlua")()
assert(ui.escrever("piscar.txt", "1") == true)
preso = true
assert(ui.escrever("piscar.txt", "1") == false)
"""
L = lua.luaL_newstate()
lua.luaL_openlibs(L)
src = b"UI_SRC = [==[" + open("plugin/ui.dlua", "rb").read() + b"]==]\n" + TESTE_UI
r = lua.luaL_loadbufferx(L, src, len(src), b"@teste_ui", b"t") or lua.lua_pcallk(L, 0, 0, 0, 0, None)
if r != 0:
    sys.exit("FALHOU: " + lua.lua_tolstring(L, -1, None).decode("utf-8", "replace"))
print("ok ui.dlua")

# retomada abre apenas links oficiais, honra a opcao local e a janela de escolha fecha após confirmar
TESTE_RETOMAR = b"""
local cfg = {dados = "123\thttps://vtt.firecast.app/artifacts/rooms/123\tSala de teste"}
local listeners, timers, abertos, arquivos, controles = {}, {}, {}, {}, {}
NDB = {load = function() return cfg end}
Firecast = {Messaging = {listen = function(nome, fn) listeners[nome] = fn end}}
GUI = {asyncOpenFirecastURI = function(uri, opcoes) abertos[#abertos + 1] = {uri, opcoes} end}
VHD = {fileExists = function(nome) return arquivos[nome] ~= nil end,
       openFile = function(nome) local valor = arquivos[nome]; return {size = #valor, read = function(_, bytes) for i = 1, #valor do bytes[i] = valor:byte(i) end return #valor end, close = function() end} end}
local UI = {escrever = function(nome, texto) arquivos[nome] = texto; return true end,
            janela = function() local f = {endUpdate = function() end, show = function() end, close = function() end}; return f, {} end,
            novo = function(_, _, props) props = props or {}; local c = {checked = props.checked, addEventListener = function(self, event, fn) self[event] = fn end}; controles[#controles + 1] = c; return c end}
setTimeout = function(fn, ms) timers[#timers + 1] = {fn = fn, ms = ms} end
require = function(n) if n == "ui.dlua" then return UI end end
local retomar = load(RETOMAR_SRC, "@retomar.dlua")()
assert(#timers == 1 and timers[1].ms == 1000)
timers[1].fn()
assert(#controles == 5 and controles[2].checked == true)
controles[2].checked = false
controles[5].onClick()
assert(arquivos["retomar.ativo"] == "0" and cfg.controleEscolhido == true)
listeners.MesaJoined({me = false, room = {firecastURI = "https://vtt.firecast.app/artifacts/rooms/456"}})
assert(not cfg.dados:find("456", 1, true))
listeners.MesaJoined({me = true, room = {firecastURI = "https://example.com/rooms/789", nome = "Nao salvar"}})
assert(not cfg.dados:find("789", 1, true))
listeners.MesaJoined({me = true, room = {firecastURI = "https://vtt.firecast.app/artifacts/rooms/456", nome = "Outra sala"}})
assert(cfg.dados:find("456\thttps://vtt.firecast.app/artifacts/rooms/456", 1, true))
assert(not cfg.dados:find("Outra sala", 1, true))
assert(#timers == 1)
controles[1].onClick()
assert(#controles == 9 and controles[6].checked == false)
controles[6].checked = true
controles[9].onClick()
assert(arquivos["retomar.ativo"] == "1")
assert(#timers == 3 and timers[2].ms == 3000 and timers[3].ms == 4500)
timers[2].fn()
assert(#abertos == 1 and abertos[1][1] == "https://vtt.firecast.app/artifacts/rooms/123")
assert(abertos[1][2].newTab and abertos[1][2].autoFocus)
listeners.MesaParted({me = false, room = {firecastURI = "https://vtt.firecast.app/artifacts/rooms/456"}})
assert(cfg.dados:find("456", 1, true))
listeners.MesaParted({me = true, room = {firecastURI = "https://vtt.firecast.app/artifacts/rooms/456"}})
assert(not cfg.dados:find("456", 1, true))
local antes = #abertos
arquivos["retomar.ativo"] = "0"
local retomarDesligado = load(RETOMAR_SRC, "@retomar_desligado.dlua")()
timers[4].fn()
assert(#abertos == antes)
"""
L = lua.luaL_newstate()
lua.luaL_openlibs(L)
src = b"RETOMAR_SRC = [==[" + open("plugin/retomar.dlua", "rb").read() + b"]==]\n" + TESTE_RETOMAR
r = lua.luaL_loadbufferx(L, src, len(src), b"@teste_retomar", b"t") or lua.lua_pcallk(L, 0, 0, 0, 0, None)
if r != 0:
    sys.exit("FALHOU: " + lua.lua_tolstring(L, -1, None).decode("utf-8", "replace"))
print("ok retomar.dlua")
