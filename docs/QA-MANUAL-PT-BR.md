# Roteiro de validação manual em transmissões reais (PT-BR)

> **Estado:** roteiro, não evidência de testes executados. Preencher os resultados apenas depois de testar o programa. A suíte automatizada não substitui uma live real. Acompanhar os resultados na [issue #75](https://github.com/felipinhobxd/Sindrome-Chat-Overlay/issues/75).

## 1. Preparação e versão correta

1. Anote **commit, versão, Windows/Android, modelo do aparelho e data**. Sempre associe o resultado ao commit testado.
2. Para testar correções novas da branch `main`, **não use uma Release antiga**: ela pode ter sido produzida antes das mudanças. No Windows, use o código atualizado com Python 3.12: `python -m pip install -r requirements.txt` e `python main.py` (veja também `RUN_APP.bat` e o [README](../README.md)). No Android, abra o último workflow verde **Build Android APK** da `main` e baixe o artifact `SindromeChatOverlay-Android-debug-v...` para testar o commit correspondente.
3. APKs de debug podem usar assinatura diferente da Release: **não desinstale o aplicativo nem apague configurações sem antes fazer backup**. Se não for possível instalar lado a lado, use outro aparelho de teste. Um build de debug não comprova atualização de APK assinado.
4. Tenha uma live pública **realmente ao vivo**, com chat habilitado, e permissão para enviar mensagens de teste (preferencialmente em um canal próprio). Um vídeo antigo ou uma live encerrada não valida o recebimento ao vivo.
5. Não envie senhas, tokens, chaves da YouTube Data API, chaves de stream, arquivo `.jks`, cookies ou logs não revisados ao GitHub. Se houver erro, **redija** as informações sensíveis antes de compartilhar a evidência.

Para cada cenário, marque **PASSOU / FALHOU / NÃO EXECUTADO / NÃO SE APLICA**. Não registre `PASSOU` quando não havia live, emote, evento de moderação, credenciais ou dispositivo disponível.

## 2. Twitch no Windows (conexão IRC TLS 6697)

**T01 — Mensagens, reconexão e canais.** Configure o canal e confirme `connected`. Peça a um participante autorizado que mande `teste 10-01 olá 😀` durante a live; confira autor, texto, horário e ausência de duplicatas. Desconecte temporariamente a rede e restabeleça-a: a aplicação deve reconectar, sem congelar a interface. Troque para outro canal válido e volte; mensagens do canal anterior não devem contaminar a nova sessão.

**T02 — Emotes nativos e de terceiros.** Envie um emote nativo da Twitch e emotes **conhecidos do canal** em BTTV, 7TV e FFZ (só se cada catálogo tiver um código realmente habilitado). Observe se aparecem como imagens, com fallback textual aceitável enquanto a imagem baixa. Confirme o caso corrigido na PR #76: os emotes de canal precisam carregar mesmo quando o IRC anuncia a conexão antes do `ROOMSTATE`; essa ordem de pacotes foi reproduzida nos testes automatizados, e aqui se valida o resultado visível em produção. Caso o canal não tenha determinado catálogo, marque `NÃO SE APLICA`, não `PASSOU`.

**T03 — Moderação.** Em canal que você administra, envie mensagem descartável e apague-a. Ela deve sair do overlay. Se autorizado, teste um timeout/ban em conta de teste para remover o histórico desse autor, sem apagar o chat de outros participantes. Não aplique moderação em usuários reais só para testar.

## 3. YouTube (modo compatibilidade e API oficial)

**Y01 — Sem chave.** Remova a **Data API key** das configurações e informe o link completo da transmissão pública (ou o canal com live ativa). Confirme o status de `compatibility`/compatibilidade e o recebimento de mensagens em ordem, inclusive acentos e emojis. Se a transmissão terminar, o aplicativo deve mostrar o estado correto e ser capaz de resolver uma nova live ao reutilizar a URL do canal.

**Y02 — Streaming oficial, opcional.** Com uma chave **YouTube Data API válida da sua propriedade** (não use Stream Key), confirme que o modo apresentado é o oficial. Envie duas mensagens diferentes; observe o recebimento e possíveis duplicatas após uma reconexão. Se houver evento legítimo de moderador, membro ou Super Chat, confira o destaque. **Não compre Super Chat apenas para realizar o teste.** Esses recursos devem ficar `NÃO EXECUTADO` se não ocorrerem naturalmente.

**Y03 — Falhas e recuperação.** Durante uma transmissão de teste, desligue brevemente a conexão e reconecte. Verifique que o chat volta a avançar. Se o transporte gRPC não estiver disponível na rede de teste, registre se ocorreu fallback para polling e qual modo foi exibido. Chave inválida deve mostrar estado de erro sem expor o segredo. Não contorne quotas do YouTube com repetidas tentativas automáticas.

## 4. Fonte OBS no Windows

**O01 — Browser Source real.** Ative a fonte OBS nas configurações do overlay. No OBS Studio, adicione **Browser Source**, cole a URL **localhost** copiada do aplicativo (por exemplo `http://127.0.0.1:8765/obs-chat`, porta real pode diferir), e defina largura e altura suficientes. Com Twitch + YouTube recebendo mensagens simultaneamente, confira atualização visual, nome, plataforma, badge, emoji/emote, ordem e fundo transparente. Compare o OBS com a janela do overlay.

**O02 — Limpeza e moderação.** Apague uma mensagem de teste na Twitch ou no YouTube; confirme que desaparece também no OBS. A limpeza de uma plataforma não deve eliminar mensagens da outra. Teste o botão de limpar mensagens localmente e reconecte; mensagens antigas duplicadas não devem reaparecer.

**O03 — Localhost e revisão de estado.** O serviço deve escutar somente em `127.0.0.1`, não em `0.0.0.0`. Opcionalmente, no próprio PC, execute `curl.exe -i http://127.0.0.1:8765/health` (substitua a porta). Espere HTTP 200. Envie um cabeçalho Host inválido, por exemplo `curl.exe -i -H "Host: exemplo-invalido.test" http://127.0.0.1:8765/health`: espere HTTP 403. Não publique o retorno bruto de `/api/state`, pois ele pode conter mensagens e nomes de pessoas.

## 5. Android em aparelho físico

**A01 — APK identificado.** Confirme a versão/commit do artifact que instalou, a versão do Android e o modelo. Abra o aplicativo; valide o chat na tela normal e, concedendo permissão `Display over other apps`, o overlay flutuante e sua notificação de serviço em primeiro plano. Teste mover, redimensionar, bloquear toque e reabrir.

**A02 — Rede e imagens.** Com live real, alterne Wi-Fi/dados móveis ou desconecte e reconecte. Verifique se mensagens, emotes e avatares voltam a aparecer sem congelamento, consumo anormal aparente ou crash. Registre o que ocorreu com links/imagens lentos e eventual falha de carregamento. A biblioteca OkHttp 5 é usada nesta versão.

**A03 — APK assinado (se disponível).** Caso tenha um APK de Release assinado pela **mesma chave da versão instalada**, instale como atualização e confirme que configuração e conexões sobrevivem. Se não houver assinatura disponível, marque `NÃO EXECUTADO`. Não gere uma nova chave de assinatura para substituir a oficial nem envie o keystore.

## 6. Registro e critérios de aceitação

| Caso | Resultado | Evidência resumida / observações |
| --- | --- | --- |
| T01 — Twitch mensagens e reconexão | NÃO EXECUTADO | |
| T02 — Twitch emotes e catálogos | NÃO EXECUTADO | |
| T03 — Twitch moderação | NÃO EXECUTADO | |
| Y01 — YouTube compatibilidade | NÃO EXECUTADO | |
| Y02 — YouTube gRPC oficial | NÃO EXECUTADO | |
| Y03 — YouTube falhas e fallback | NÃO EXECUTADO | |
| O01 — Browser Source | NÃO EXECUTADO | |
| O02 — OBS moderação e limpeza | NÃO EXECUTADO | |
| O03 — Isolamento localhost | NÃO EXECUTADO | |
| A01 — Interface e overlay Android | NÃO EXECUTADO | |
| A02 — Rede e imagens Android | NÃO EXECUTADO | |
| A03 — Atualização assinada | NÃO EXECUTADO | |

**Bloqueios de release:** crash, perda de mensagens de moderação, exposição de credenciais, fonte OBS acessível fora do loopback, app sem reconexão confiável ou regressão reproduzível de emotes. Abra uma issue com **passos, ambiente, commit, resultado esperado e obtido, e logs censurados**. Não assinale cenários não executados como aprovados.

**Conclusão:** a validação manual só estará completa depois de executar os cenários aplicáveis e preencher os resultados na [issue #75](https://github.com/felipinhobxd/Sindrome-Chat-Overlay/issues/75).
