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
        "show_api_key": "Show API key",
        "hide_api_key": "Hide API key",
        "channel": "Channel:",
        "channel_or_live": "Channel or live stream:",
        "advanced_settings": "Advanced settings",
        "youtube_data_api_key_optional": "YouTube Data API Key (optional)",
        "youtube_key_description": (
            "Optional. Allows the official YouTube API to receive chat with lower latency "
            "and greater stability."
        ),
        "youtube_key_clarification": (
            "This is not the Stream Key used to broadcast. The app continues to work "
            "without it."
        ),
        "youtube_mode_compatibility_title": "🔵 Compatibility mode — no API key",
        "youtube_mode_compatibility_detail": "Works without additional setup.",
        "youtube_mode_official_title": "⚡ Official API — low latency",
        "youtube_mode_official_detail": (
            "Using YouTube's official API to receive chat with lower latency."
        ),
        "youtube_mode_official_fallback_title": "⚡ Official API — fallback connection",
        "youtube_mode_official_fallback_detail": (
            "The official API is active, but the low-latency connection is temporarily "
            "unavailable."
        ),
        "youtube_key_valid_title": "⚡ Valid API key",
        "youtube_key_valid_detail": (
            "Save to use the official low-latency connection."
        ),
        "youtube_key_invalid_title": "⚠ API key invalid",
        "youtube_key_invalid_detail": (
            "This key could not be validated. Check the value you entered."
        ),
        "youtube_key_unavailable_title": "⚠ API key not verified",
        "youtube_key_unavailable_detail": "The API key could not be verified right now.",
        "youtube_key_checking_title": "Checking API key…",
        "youtube_key_checking_detail": "This does not interrupt the current chat connection.",
        "youtube_mode_fallback_title": "🔵 Compatibility mode",
        "youtube_mode_fallback_detail": (
            "The official API is unavailable, so compatibility mode is active."
        ),
        "youtube_invalid_key_title": "Invalid YouTube API key",
        "youtube_invalid_key_save_message": (
            "Correct or remove the API key before saving. The app works without a key."
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
        "drag_overlay_hint": "Drag here to move the overlay",
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
            "Download the signed installer now? Its SHA-256 checksum and Windows signature "
            "will be verified before you are asked to run it."
        ),
        "download_update": "Download update",
        "update_downloading_title": "Downloading update",
        "update_downloading": "Downloading the signed installer…",
        "update_verifying": "Verifying checksum and Windows signature…",
        "update_ready_title": "Update verified",
        "update_ready_message": "Sindrome Chat Overlay {version} is ready to install.",
        "update_ready_details": (
            "The SHA-256 checksum and trusted Windows signature are valid. Start the "
            "installer and close the current app?"
        ),
        "install_update": "Install update",
        "update_failed_title": "Update blocked",
        "update_download_failed": (
            "The installer could not be downloaded. Check your connection and try again later."
        ),
        "update_storage_failed": "Windows could not save the downloaded installer.",
        "update_integrity_failed": (
            "The downloaded installer did not pass the SHA-256 integrity check. It will not run."
        ),
        "update_signature_failed": (
            "Windows could not validate the installer's digital signature. It will not run."
        ),
        "update_signer_failed": (
            "The installer was signed by a different publisher. It will not run."
        ),
        "update_current_signature_failed": (
            "The current app signature could not be validated, so a safe automatic update "
            "cannot continue."
        ),
        "update_changed_failed": (
            "The installer changed after verification. It was blocked and will not run."
        ),
        "update_unknown_failed": "The update could not be verified and will not run.",
        "open_update_page": "Open official release page",
        "later": "Later",
        "update_launch_failed_title": "Could not start the installer",
        "update_launch_failed_message": (
            "The verified installer was saved, but Windows could not start it. Try again from "
            "the official Releases page."
        ),
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
        "show_api_key": "Mostrar API Key",
        "hide_api_key": "Esconder API Key",
        "channel": "Canal:",
        "channel_or_live": "Canal ou live:",
        "advanced_settings": "Configurações avançadas",
        "youtube_data_api_key_optional": "YouTube Data API Key (opcional)",
        "youtube_key_description": (
            "Opcional. Permite usar a API oficial do YouTube para obter o chat com menor "
            "latência e maior estabilidade."
        ),
        "youtube_key_clarification": (
            "Não é a Stream Key usada para transmitir. O aplicativo continua funcionando "
            "sem ela."
        ),
        "youtube_mode_compatibility_title": "🔵 Modo compatibilidade — sem API Key",
        "youtube_mode_compatibility_detail": "Funciona sem configuração adicional.",
        "youtube_mode_official_title": "⚡ API oficial — baixa latência",
        "youtube_mode_official_detail": (
            "Usando a API oficial do YouTube para receber o chat com menor latência."
        ),
        "youtube_mode_official_fallback_title": "⚡ API oficial — conexão alternativa",
        "youtube_mode_official_fallback_detail": (
            "A API oficial está ativa, mas a conexão de baixa latência está temporariamente "
            "indisponível."
        ),
        "youtube_key_valid_title": "⚡ API Key válida",
        "youtube_key_valid_detail": (
            "Salve para usar a conexão oficial de baixa latência."
        ),
        "youtube_key_invalid_title": "⚠ API Key inválida",
        "youtube_key_invalid_detail": (
            "Não foi possível validar esta chave. Verifique o valor informado."
        ),
        "youtube_key_unavailable_title": "⚠ API Key não verificada",
        "youtube_key_unavailable_detail": "Não foi possível verificar a API Key agora.",
        "youtube_key_checking_title": "Verificando a API Key…",
        "youtube_key_checking_detail": "Isso não interrompe a conexão atual do chat.",
        "youtube_mode_fallback_title": "🔵 Modo compatibilidade",
        "youtube_mode_fallback_detail": (
            "A API oficial está indisponível; o modo compatibilidade está ativo."
        ),
        "youtube_invalid_key_title": "API Key do YouTube inválida",
        "youtube_invalid_key_save_message": (
            "Corrija ou remova a API Key antes de salvar. O aplicativo funciona sem chave."
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
        "drag_overlay_hint": "Arraste aqui para mover o overlay",
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
            "Deseja baixar o instalador assinado agora? O SHA-256 e a assinatura do Windows "
            "serão verificados antes de perguntar se deseja executá-lo."
        ),
        "download_update": "Baixar atualização",
        "update_downloading_title": "Baixando atualização",
        "update_downloading": "Baixando o instalador assinado…",
        "update_verifying": "Verificando SHA-256 e assinatura do Windows…",
        "update_ready_title": "Atualização verificada",
        "update_ready_message": "O Sindrome Chat Overlay {version} está pronto para instalar.",
        "update_ready_details": (
            "O SHA-256 e a assinatura confiável do Windows são válidos. Deseja iniciar o "
            "instalador e fechar o aplicativo atual?"
        ),
        "install_update": "Instalar atualização",
        "update_failed_title": "Atualização bloqueada",
        "update_download_failed": (
            "Não foi possível baixar o instalador. Verifique a conexão e tente novamente depois."
        ),
        "update_storage_failed": "O Windows não conseguiu salvar o instalador baixado.",
        "update_integrity_failed": (
            "O instalador baixado não passou na verificação SHA-256. Ele não será executado."
        ),
        "update_signature_failed": (
            "O Windows não conseguiu validar a assinatura digital do instalador. Ele não será "
            "executado."
        ),
        "update_signer_failed": (
            "O instalador foi assinado por outro fornecedor. Ele não será executado."
        ),
        "update_current_signature_failed": (
            "Não foi possível validar a assinatura do aplicativo atual; por segurança, a "
            "atualização automática não pode continuar."
        ),
        "update_changed_failed": (
            "O instalador mudou depois da verificação. Ele foi bloqueado e não será executado."
        ),
        "update_unknown_failed": "Não foi possível verificar a atualização. Ela não será executada.",
        "open_update_page": "Abrir página oficial da versão",
        "later": "Mais tarde",
        "update_launch_failed_title": "Não foi possível iniciar o instalador",
        "update_launch_failed_message": (
            "O instalador verificado foi salvo, mas o Windows não conseguiu iniciá-lo. Tente "
            "novamente pela página oficial de Releases."
        ),
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
