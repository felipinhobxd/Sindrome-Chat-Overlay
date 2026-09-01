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
        "youtube_data_api_key": "YouTube Data API key (optional):",
        "youtube_source_note": (
            "The channel/live URL is used to discover the active Video ID automatically. "
            "With an API key, the official API then discovers the Live Chat ID; you do not "
            "need to enter either ID."
        ),
        "youtube_key_note": (
            "Optional: enables the official low-latency streamList connection. This is a "
            "YouTube Data API v3 key, not a Stream Key. Stream Keys are never used to read "
            "chat. On Windows, the value is protected for your account with DPAPI and is "
            "never written to logs."
        ),
        "always_on_top": "Always on top",
        "start_click_through": "Start with mouse clicks locked",
        "auto_scroll": "Automatically scroll when a message arrives",
        "sound_enabled": "Play a sound when a message arrives",
        "check_for_updates": "Automatically check for application updates",
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
        "hotkey_unavailable_title": "Global shortcut unavailable",
        "hotkey_unavailable_message": (
            "Another program is using Ctrl + Shift + O. The shortcut will work only while "
            "Sindrome Chat Overlay is active until the conflict is removed."
        ),
        "update_available_title": "Update available",
        "update_available_message": (
            "Sindrome Chat Overlay {version} is available. You are using version {current}."
        ),
        "update_available_details": (
            "Would you like to open the official GitHub release page to download the update?"
        ),
        "open_update_page": "Open download page",
        "later": "Later",
        "update_open_failed_title": "Could not open the update",
        "update_open_failed_message": (
            "Open the Sindrome Chat Overlay Releases page in your browser to update manually."
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
        "live_official_streaming": "Live · official low-latency stream",
        "live_official_polling": "Live · official polling fallback",
        "youtube_chat_disabled": "live chat is disabled; checking again in 60s",
        "youtube_chat_invalid": "invalid live chat; checking for a new live stream",
        "youtube_api_key_rejected": "YouTube Data API key rejected; retrying in 60s",
        "youtube_chat_unavailable": "live chat unavailable; checking again in 30s",
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
        "youtube_data_api_key": "Chave da YouTube Data API (opcional):",
        "youtube_source_note": (
            "O link do canal/live descobre automaticamente o Video ID da live ativa. Com uma "
            "chave da API, a API oficial descobre o Live Chat ID; você não precisa informar "
            "nenhum dos IDs."
        ),
        "youtube_key_note": (
            "Opcional: ativa a conexão oficial streamList de baixa latência. Esta é uma chave "
            "da YouTube Data API v3, não uma Chave de Transmissão (Stream Key). Stream Key "
            "nunca é usada para ler o chat. No Windows, o valor é protegido para sua conta "
            "com DPAPI e nunca é gravado nos logs."
        ),
        "always_on_top": "Manter sempre no topo",
        "start_click_through": "Iniciar com os cliques bloqueados",
        "auto_scroll": "Rolar automaticamente ao receber mensagem",
        "sound_enabled": "Tocar som ao receber mensagem",
        "check_for_updates": "Verificar atualizações do aplicativo automaticamente",
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
        "hotkey_unavailable_title": "Atalho global indisponível",
        "hotkey_unavailable_message": (
            "Outro programa está usando Ctrl + Shift + O. Até o conflito ser removido, o "
            "atalho funcionará somente quando o Sindrome Chat Overlay estiver ativo."
        ),
        "update_available_title": "Atualização disponível",
        "update_available_message": (
            "O Sindrome Chat Overlay {version} está disponível. Você está usando a versão "
            "{current}."
        ),
        "update_available_details": (
            "Deseja abrir a página oficial da versão no GitHub para baixar a atualização?"
        ),
        "open_update_page": "Abrir página de download",
        "later": "Mais tarde",
        "update_open_failed_title": "Não foi possível abrir a atualização",
        "update_open_failed_message": (
            "Abra a página Releases do Sindrome Chat Overlay no navegador para atualizar "
            "manualmente."
        ),
        "connecting": "Conectando…",
        "reconnecting": "Reconectando em {seconds}s",
        "disconnected": "Desconectado",
        "live": "Ao vivo",
        "connected": "Conectado",
        "searching_live": "Procurando a live…",
        "waiting_next_live": "Aguardando a próxima live",
        "rate_limited": "YouTube limitou o acesso; tentando em 60s",
        "live_auto": "Ao vivo · modo automático",
        "live_official_streaming": "Ao vivo · stream oficial de baixa latência",
        "live_official_polling": "Ao vivo · polling oficial de contingência",
        "youtube_chat_disabled": "chat desativado; verificando novamente em 60s",
        "youtube_chat_invalid": "chat inválido; procurando uma nova live",
        "youtube_api_key_rejected": "chave da YouTube Data API recusada; nova tentativa em 60s",
        "youtube_chat_unavailable": "chat indisponível; verificando novamente em 30s",
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
