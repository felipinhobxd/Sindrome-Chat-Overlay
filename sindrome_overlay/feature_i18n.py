from __future__ import annotations

from typing import Any

_TEXT: dict[str, dict[str, str]] = {
    "en": {
        "profiles": "Overlay profiles",
        "profiles_menu": "Overlay profiles",
        "profiles_help": (
            "Save and switch complete overlay layouts without changing your Twitch or YouTube "
            "channel credentials. Custom profiles remember size, position and appearance."
        ),
        "profile": "Profile:",
        "profile_apply": "Apply",
        "profile_save_current": "Save current as…",
        "profile_delete": "Delete",
        "profile_name_title": "Save overlay profile",
        "profile_name_prompt": "Profile name:",
        "profile_invalid_name": "Use a profile name between 1 and 40 characters.",
        "profile_limit": "You can keep up to {count} custom overlay profiles.",
        "profile_exists_title": "Profile already exists",
        "profile_exists_message": "Replace the existing profile “{name}”?",
        "profile_delete_title": "Delete overlay profile",
        "profile_delete_message": "Delete the custom profile “{name}”?",
        "profile_compact_fps": "Compact FPS",
        "profile_chat_focus": "Chat Focus",
        "profile_clean_stream": "Clean Stream",
        "diagnostics": "Diagnostics",
        "diagnostics_help": (
            "Creates a ZIP for troubleshooting with app/system state and recent logs. API keys, "
            "channel/live identifiers, home-directory paths and chat messages are not included."
        ),
        "export_diagnostics": "Export diagnostic ZIP…",
        "diagnostic_save_title": "Export diagnostic",
        "diagnostic_saved_title": "Diagnostic exported",
        "diagnostic_saved_message": "Diagnostic package saved to:\n{path}",
        "diagnostic_failed_title": "Could not export diagnostic",
        "diagnostic_failed_message": "The diagnostic package could not be created.\n\n{error}",
    },
    "pt-BR": {
        "profiles": "Perfis de Overlay",
        "profiles_menu": "Perfis de Overlay",
        "profiles_help": (
            "Salve e troque layouts completos do overlay sem alterar as credenciais/canais da "
            "Twitch ou do YouTube. Perfis personalizados lembram tamanho, posição e aparência."
        ),
        "profile": "Perfil:",
        "profile_apply": "Aplicar",
        "profile_save_current": "Salvar atual como…",
        "profile_delete": "Excluir",
        "profile_name_title": "Salvar perfil de Overlay",
        "profile_name_prompt": "Nome do perfil:",
        "profile_invalid_name": "Use um nome de perfil entre 1 e 40 caracteres.",
        "profile_limit": "Você pode manter até {count} perfis personalizados de Overlay.",
        "profile_exists_title": "O perfil já existe",
        "profile_exists_message": "Substituir o perfil existente “{name}”?",
        "profile_delete_title": "Excluir perfil de Overlay",
        "profile_delete_message": "Excluir o perfil personalizado “{name}”?",
        "profile_compact_fps": "FPS Compacto",
        "profile_chat_focus": "Foco no Chat",
        "profile_clean_stream": "Stream Limpa",
        "diagnostics": "Diagnóstico",
        "diagnostics_help": (
            "Cria um ZIP para suporte com estado do app/sistema e logs recentes. API Keys, "
            "identificadores de canal/live, caminhos da sua pasta de usuário e mensagens do chat "
            "não são incluídos."
        ),
        "export_diagnostics": "Exportar diagnóstico ZIP…",
        "diagnostic_save_title": "Exportar diagnóstico",
        "diagnostic_saved_title": "Diagnóstico exportado",
        "diagnostic_saved_message": "Pacote de diagnóstico salvo em:\n{path}",
        "diagnostic_failed_title": "Não foi possível exportar o diagnóstico",
        "diagnostic_failed_message": "O pacote de diagnóstico não pôde ser criado.\n\n{error}",
    },
}


def feature_tr(language: str, key: str, **values: Any) -> str:
    table = _TEXT.get(language) or _TEXT["en"]
    template = table.get(key) or _TEXT["en"].get(key) or key
    try:
        return template.format(**values)
    except (KeyError, ValueError):
        return template
