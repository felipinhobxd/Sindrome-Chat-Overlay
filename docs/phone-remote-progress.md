# Controle do PC pelo celular — ponto de retomada

Branch: `feat/phone-remote-control`. Base publicada: v1.9.2.
Trabalho solicitado em etapas pequenas, para economizar créditos.

Concluído:
- Contrato de comandos e estado permitido em `sindrome_overlay/remote_control.py`.
- Execução no overlay via `OverlayWindow.apply_remote_command()`, sem reiniciar
  chats; exige a thread Qt e rejeita comandos durante diálogos modais/encerramento.
- Fonte, opacidades, rolagem, perfis, click-through e limpeza do histórico local.
- Base de pareamento em `sindrome_overlay/remote_pairing.py`: código de uso único
  por 2 minutos, 5 tentativas, uma sessão de 8 horas e revogação. Tudo em memória.
- Tela local em `sindrome_overlay/ui/remote_pairing_dialog.py`, em português e
  inglês: gerar código, contagem regressiva, estado de autorização e revogação.
  Fechar, ocultar ou pressionar Esc cancela o código pendente e para o timer,
  preservando um celular já autorizado. Estado público não contém credenciais.
- Corrigidos callbacks de layout pendentes após destruir o chat: os timers agora
  usam o objeto Qt como contexto, com teste de regressão de destruição.

Ainda não existe conexão PC–celular. Nenhum servidor foi iniciado e nenhuma
nova versão foi publicada. A tela ainda não aparece no menu: será integrada
quando o transporte protegido estiver pronto, para não oferecer um controle
sem conexão. Nenhuma configuração ou credencial de pareamento é persistida.

Próxima etapa pequena: transporte protegido na rede local para o pareamento.
Depois: ligar ativação/desativação e a tela ao menu do PC, manter uma única
instância da tela, revogar ao desligar/encerrar, implementar a fila limitada até
a thread Qt e a interface no celular. Nunca expor códigos/tokens
em logs; não reutilizar a fonte OBS como endpoint público de controle.
Revalidar a sessão ao executar comandos na thread Qt, inclusive após revogação.

Validação focada: `python -m unittest discover -s tests -p 'test_remote*.py'` e
`python -m mypy`. Testes Qt usam `QT_QPA_PLATFORM=offscreen`.
Resultado desta etapa: 29 testes `test_remote*.py` passaram sem erros de callbacks
Qt; `test_message*.py` teve 11 aprovados e 2 exclusivos de Windows ignorados no
Linux; mypy passou em 41 arquivos.
Só integrar na main e gerar nova build quando a funcionalidade estiver completa
e os workflows Windows/Android/supply-chain passarem.
