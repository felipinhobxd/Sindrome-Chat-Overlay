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

Ainda não existe conexão PC–celular. Nenhum servidor foi iniciado e nenhuma
nova versão foi publicada. A base de pareamento ainda precisa ser integrada.

Próxima etapa pequena: interface no PC para ativar/desativar o controle,
mostrar o código e revogar a sessão. Depois: transporte protegido na rede local,
fila limitada até a thread Qt e interface no celular. Nunca expor códigos/tokens
em logs; não reutilizar a fonte OBS como endpoint público de controle.
Revalidar a sessão ao executar comandos na thread Qt, inclusive após revogação.

Validação focada: `python -m unittest discover -s tests -p 'test_remote*.py'` e
`python -m mypy`. Testes Qt usam `QT_QPA_PLATFORM=offscreen`.
Resultado desta etapa: 22 testes passaram; mypy passou em 40 arquivos.
Só integrar na main e gerar nova build quando a funcionalidade estiver completa
e os workflows Windows/Android/supply-chain passarem.
