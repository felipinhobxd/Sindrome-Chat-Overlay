from __future__ import annotations

from typing import Any

DEFAULT_LANGUAGE = "en"
SUPPORTED_LANGUAGES = ("en", "pt-BR")
LANGUAGE_LABELS = {
    "en": "English",
    "pt-BR": "Português (Brasil)",
}

_TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        "settings_title": "Settings · Sindrome Chat Overlay",
        "language": "Language:",
        "language_hint": "The interface language changes after you save.",
        "channels": "Channels",
        "appearance": "Appearance",
        "global_shortcut_hint": (
            "Global shortcut: Ctrl + Shift + O locks or unlocks mouse clicks on the overlay."
        ),
        "restore_defaults": "Restore defaults",
        "save": "Save",
        "cancel": "Cancel",
        "show_twitch_messages": "Show Twitch messages",
        "twitch_placeholder": "sindromegames or channel URL",
        "twitch_readonly_note": "Public, anonymous read-only access; the app never sends messages.",
        "show_youtube_chat": "Show YouTube live chat",
        "youtube_placeholder": "@Channel, channel URL, or live stream URL",
        "optional": "Optional",
        "show_key": "Show key",
        "channel": "Channel:",
        "channel_or_live": "Channel or live stream:",
        "api_key": "API key:",
        "youtube_key_note": (
            "Without a key, automatic mode reads the public chat. Your own YouTube Data API "
            "key is optional and enables official API mode. Never embed a personal key in an "
            ".exe that you share."
        ),
        "always_on_top": "Always on top",
        "start_click_through": "Start with mouse clicks locked",
        "auto_scroll": "Automatically scroll when a message arrives",
        "sound_enabled": "Play a sound when a message arrives",
        "show_timestamps": "Show timestamps",
        "show_platform": "Show Twitch / YouTube on each message",
        "hide_commands": "Hide messages that start with !",
        "panel_opacity": "Panel opacity:",
        "message_opacity": "Message opacity:",
        "font_size": "Font size:",
        "max_messages": "Maximum messages:",
        "remove_after": "Remove messages after:",
        "never_remove": "Never remove",
        "no_channel_title": "No channel enabled",
        "no_channel_message": "Enable Twitch, YouTube, or both.",
        "invalid_settings_title": "Invalid settings",
        "initializing": "initializing",
        "disabled": "disabled",
        "clear_messages": "Clear messages",
        "open_settings": "Open settings",
        "lock_clicks": "Lock mouse clicks (Ctrl+Shift+O)",
        "unlock_clicks": "Unlock mouse clicks (Ctrl+Shift+O)",
        "close": "Close",
        "empty_state": (
            "Waiting for messages…\n\n"
            "Twitch and YouTube will appear together here.\n"
            "Ctrl + Shift + O locks or unlocks mouse clicks."
        ),
        "show_hide": "Show / hide",
        "settings": "Settings",
        "quit": "Quit",
        "locked_title": "Overlay locked",
        "locked_message": (
            "Press Ctrl + Shift + O or use the system tray icon to unlock mouse clicks."
        ),
        "connecting": "Connecting…",
        "reconnecting": "Reconnecting in {seconds}s",
        "disconnected": "Disconnected",
        "live": "Live",
        "connected": "Connected",
        "searching_live": "Looking for a live stream…",
        "waiting_next_live": "Waiting for the next live stream",
        "rate_limited": "YouTube limited access; retrying in 60s",
        "live_auto": "Live · automatic mode",
        "live_official": "Live · official API",
        "unexpected_error": (
            "The application encountered an unexpected error.\n\n"
            "Close and reopen it. The overlay.log file may help diagnose the problem."
        ),
        "twitch_event": "Twitch event",
        "super_chat_sent": "Sent a Super Chat / Super Sticker",
        "super_chat": "Sent a Super Chat",
        "super_sticker": "Sent a Super Sticker",
        "became_member": "Became a channel member",
        "member_event": "Channel membership event",
        "badge_member": "MEMBER",
        "badge_owner": "OWNER",
        "error_twitch_required": "Enter a Twitch channel.",
        "error_twitch_url": "Use a valid Twitch URL.",
        "error_twitch_name": "The Twitch channel name appears to be invalid.",
        "error_youtube_required": "Enter a YouTube channel or video.",
        "error_youtube_short_url": "The shortened YouTube URL appears to be invalid.",
        "error_youtube_url": "Use a valid YouTube URL.",
        "error_youtube_video_url": "The YouTube video URL appears to be invalid.",
        "error_youtube_specific_channel": "Enter a specific YouTube channel.",
    },
    "pt-BR": {
        "settings_title": "Configurações · Sindrome Chat Overlay",
        "language": "Idioma:",
        "language_hint": "O idioma da interface muda depois que você salvar.",
        "channels": "Canais",
        "appearance": "Aparência",
        "global_shortcut_hint": (
            "Atalho global: Ctrl + Shift + O bloqueia ou desbloqueia os cliques no overlay."
        ),
        "restore_defaults": "Restaurar padrão",
        "save": "Salvar",
        "cancel": "Cancelar",
        "show_twitch_messages": "Mostrar mensagens da Twitch",
        "twitch_placeholder": "sindromegames ou link do canal",
        "twitch_readonly_note": (
            "Leitura pública, anônima e somente leitura; o aplicativo nunca envia mensagens."
        ),
        "show_youtube_chat": "Mostrar o chat ao vivo do YouTube",
        "youtube_placeholder": "@Canal, link do canal ou link da live",
        "optional": "Opcional",
        "show_key": "Mostrar chave",
        "channel": "Canal:",
        "channel_or_live": "Canal ou live:",
        "api_key": "Chave da API:",
        "youtube_key_note": (
            "Sem chave, o modo automático lê o chat público. Uma chave própria da YouTube "
            "Data API é opcional e ativa o modo oficial. Nunca coloque uma chave pessoal "
            "dentro de um .exe que será compartilhado."
        ),
        "always_on_top": "Manter sempre no topo",
        "start_click_through": "Iniciar com os cliques bloqueados",
        "auto_scroll": "Rolar automaticamente ao receber mensagem",
        "sound_enabled": "Tocar som ao receber mensagem",
        "show_timestamps": "Mostrar horário",
        "show_platform": "Mostrar Twitch / YouTube em cada mensagem",
        "hide_commands": "Ocultar mensagens que começam com !",
        "panel_opacity": "Opacidade do painel:",
        "message_opacity": "Opacidade das mensagens:",
        "font_size": "Tamanho da fonte:",
        "max_messages": "Máximo de mensagens:",
        "remove_after": "Apagar mensagens após:",
        "never_remove": "Nunca apagar",
        "no_channel_title": "Nenhum canal ativado",
        "no_channel_message": "Ative Twitch, YouTube ou ambos.",
        "invalid_settings_title": "Configuração inválida",
        "initializing": "iniciando",
        "disabled": "desativado",
        "clear_messages": "Limpar mensagens",
        "open_settings": "Abrir configurações",
        "lock_clicks": "Bloquear cliques (Ctrl+Shift+O)",
        "unlock_clicks": "Desbloquear cliques (Ctrl+Shift+O)",
        "close": "Fechar",
        "empty_state": (
            "Aguardando mensagens…\n\n"
            "Twitch e YouTube aparecerão juntos aqui.\n"
            "Ctrl + Shift + O bloqueia ou libera os cliques."
        ),
        "show_hide": "Mostrar / ocultar",
        "settings": "Configurações",
        "quit": "Sair",
        "locked_title": "Overlay bloqueado",
        "locked_message": ("Use Ctrl + Shift + O ou o ícone ao lado do relógio para desbloquear."),
        "connecting": "Conectando…",
        "reconnecting": "Reconectando em {seconds}s",
        "disconnected": "Desconectado",
        "live": "Ao vivo",
        "connected": "Conectado",
        "searching_live": "Procurando a live…",
        "waiting_next_live": "Aguardando a próxima live",
        "rate_limited": "YouTube limitou o acesso; tentando em 60s",
        "live_auto": "Ao vivo · modo automático",
        "live_official": "Ao vivo · API oficial",
        "unexpected_error": (
            "O aplicativo encontrou um erro inesperado.\n\n"
            "Feche e abra novamente. O arquivo overlay.log pode ajudar no diagnóstico."
        ),
        "twitch_event": "Evento da Twitch",
        "super_chat_sent": "Enviou um Super Chat / Super Sticker",
        "super_chat": "Enviou um Super Chat",
        "super_sticker": "Enviou um Super Sticker",
        "became_member": "Tornou-se membro do canal",
        "member_event": "Evento de membro do canal",
        "badge_member": "MEMBRO",
        "badge_owner": "DONO",
        "error_twitch_required": "Informe o canal da Twitch.",
        "error_twitch_url": "Use um link válido da Twitch.",
        "error_twitch_name": "O nome do canal da Twitch parece inválido.",
        "error_youtube_required": "Informe o canal ou vídeo do YouTube.",
        "error_youtube_short_url": "O link curto do YouTube parece inválido.",
        "error_youtube_url": "Use um link válido do YouTube.",
        "error_youtube_video_url": "O link do vídeo do YouTube parece inválido.",
        "error_youtube_specific_channel": "Informe um canal específico do YouTube.",
    },
}


def normalize_language(language: Any) -> str:
    return language if language in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


def tr(language: str, key: str, **values: Any) -> str:
    normalized = normalize_language(language)
    template = _TRANSLATIONS[normalized].get(key) or _TRANSLATIONS[DEFAULT_LANGUAGE].get(key, key)
    return template.format(**values) if values else template


def translation_keys(language: str) -> frozenset[str]:
    return frozenset(_TRANSLATIONS[normalize_language(language)])
