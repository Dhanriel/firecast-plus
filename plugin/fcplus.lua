require("firecast.lua")
local Cores = require("cores.dlua")
local Palavras = require("palavras.dlua")
local Piscar = require("piscar.dlua")
local Previa = require("previa.dlua")
local Turno = require("turno.dlua")
require("tokens.dlua") -- registra os botoes "Meu token" nos mapas

local AJUDA = {
	{comando = "/fc", descricao = "Lista os comandos do Firecast Plus."},
	{comando = "/cores", descricao = "Abre a janela para mudar as cores, a fonte e o tamanho do chat do Firecast (também no botão da barra do chat)."},
	{comando = "/beep", descricao = "Abre a lista de palavras que tocam um beep quando alguém escreve (também na barra do chat)."},
	{comando = "Mapa: Meu token", descricao = "Botões na barra do mapa para criar/remover o seu token (jogador precisa de um mestre com o plugin)."},
	{comando = "/piscar", descricao = "Escolhe por mesa e por aba quem faz o ícone piscar na barra de tarefas (também na barra do chat)."},
	{comando = "/previa", descricao = "Liga/desliga a prévia de imagens e vídeos do YouTube no chat (também na barra do chat)."},
	{comando = "/turno", descricao = "Rastreador de turno: o mestre monta a ordem e avança; o jogador da vez recebe beep e aviso."},
	{comando = "/multi N rolagem [texto]", descricao = "Rola a mesma rolagem N vezes. Ex: /multi 3 1d20+5 ataque"},
	{comando = "/sorteio [texto]", descricao = "Sorteia um jogador da mesa e anuncia no chat."},
	{comando = "/timer segundos [texto]", descricao = "Lembrete local depois de X segundos (so voce ve)."},
}

local function aparar(s)
	return (tostring(s or ""):gsub("^%s+", ""):gsub("%s+$", ""))
end

local function comandoAjuda(chat)
	chat:escrever("Comandos:")
	for _, a in ipairs(AJUDA) do
		chat:escrever("  " .. a.comando .. " - " .. a.descricao)
	end
end

local function comandoMulti(chat, p)
	local n, rolagem, texto = p:match("^(%d+)%s+(%S+)%s*(.*)$")
	n = tonumber(n)
	if n == nil or n < 1 or n > 20 then
		chat:escrever("Uso: /multi N rolagem [texto] (N de 1 a 20)")
		return
	end
	for i = 1, n do
		chat:rolarDados(rolagem, aparar(texto .. " #" .. i))
	end
end

local function comandoSorteio(chat, mesa, p)
	local nicks = {}
	for _, j in ipairs(mesa.jogadores or {}) do
		if j.nick ~= nil then nicks[#nicks + 1] = j.nick end
	end
	if #nicks == 0 then
		chat:escrever("Ninguem na mesa para sortear.")
		return
	end
	local msg = "Sorteado: " .. nicks[math.random(#nicks)]
	if p ~= "" then msg = msg .. " (" .. p .. ")" end
	chat:enviarMensagem(msg)
end

local function comandoTimer(chat, p)
	local seg, texto = p:match("^(%d+)%s*(.*)$")
	seg = tonumber(seg)
	if seg == nil or seg < 1 then
		chat:escrever("Uso: /timer segundos [texto]")
		return
	end
	if texto == "" then texto = "Tempo esgotado!" end
	chat:escrever("Timer de " .. seg .. "s iniciado.")
	setTimeout(function() chat:escrever("⏰ " .. texto) end, seg * 1000)
end

Firecast.Messaging.listen("HandleChatCommand", function(message)
	local mesa = message.mesa
	if mesa == nil then return end
	local chat = message.chat or mesa.activeChat
	local cmd = string.lower(tostring(message.comando or ""))
	local p = aparar(message.parametro)

	if cmd == "fc" then
		comandoAjuda(chat)
	elseif cmd == "cores" then
		Cores.abrir()
	elseif cmd == "beep" then
		Palavras.abrir()
	elseif cmd == "piscar" then
		Piscar.abrir()
	elseif cmd == "previa" then
		Previa.abrir()
	elseif cmd == "turno" then
		Turno.abrir(mesa)
	elseif cmd == "multi" then
		comandoMulti(chat, p)
	elseif cmd == "sorteio" then
		comandoSorteio(chat, mesa, p)
	elseif cmd == "timer" then
		comandoTimer(chat, p)
	else
		return
	end
	message.response = {handled = true}
end)

Firecast.Messaging.listen("ListChatCommands", function(message)
	message.response = AJUDA
end)

Firecast.registerChatToolButton({
	hint = "Cores e fonte do Firecast (Firecast Plus)",
	icon = "/icons/cores.png",
	group = "fcplus",
	callback = function(chat) Cores.abrir() end,
})

Firecast.registerChatToolButton({
	hint = "Beep por palavra (Firecast Plus)",
	icon = "/icons/beep.png",
	group = "fcplus",
	callback = function(chat) Palavras.abrir() end,
})

Firecast.registerChatToolButton({
	hint = "Piscar na barra de tarefas (Firecast Plus)",
	icon = "/icons/piscar.png",
	group = "fcplus",
	callback = function(chat) Piscar.abrir() end,
})

Firecast.registerChatToolButton({
	hint = "Prévia de links (Firecast Plus)",
	icon = "/icons/previa.png",
	group = "fcplus",
	callback = function(chat) Previa.abrir() end,
})
