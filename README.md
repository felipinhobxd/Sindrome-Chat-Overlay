# Sindrome Chat Overlay

Overlay transparente para Windows que reúne, em uma única janela, as mensagens ao vivo da **Twitch** e do **YouTube**. O projeto já vem configurado com:

- Twitch: `sindromegames`
- YouTube: `https://www.youtube.com/@SindromeGames/live`

O aplicativo é somente leitura: ele não envia mensagens, não pede senha das plataformas e não registra o conteúdo do chat em arquivos.

## O que já funciona

- Twitch e YouTube simultaneamente, ordenados conforme chegam ao computador.
- Detecção automática da transmissão ativa quando é informado um canal do YouTube.
- Identificação visual de Twitch, YouTube, moderadores, membros, Bits, Super Chats e eventos de inscrição.
- Reconexão automática se a internet ou uma das plataformas oscilar.
- Rolagem automática que mantém a mensagem mais nova visível.
- Som curto para cada nova mensagem, vindo da Twitch ou do YouTube.
- Remoção da mensagem no overlay quando a plataforma informa que ela foi apagada.
- Janela sem borda, transparente, redimensionável e sempre no topo.
- Modo de clique através para jogar sem o overlay capturar o mouse.
- Atalho global `Ctrl + Shift + O` para bloquear ou desbloquear os cliques.
- Ícone ao lado do relógio com mostrar/ocultar, configurações e sair.
- Fonte, transparência, quantidade e tempo de permanência das mensagens configuráveis.
- Configurações salvas para a próxima abertura.
- Log técnico rotativo em `%APPDATA%\SindromeChatOverlay\overlay.log`.

> O YouTube mostra o **chat da transmissão ao vivo**, não os comentários comuns publicados abaixo de vídeos gravados.

## Testar sem gerar o EXE

1. Instale o [Python 3.12 de 64 bits](https://www.python.org/downloads/windows/) e marque **Add Python to PATH** durante a instalação.
2. Dê dois cliques em `INICIAR.bat`.
3. Na primeira execução, aguarde a instalação automática das dependências.

## Gerar o `.exe` automaticamente

1. Instale o Python 3.12 de 64 bits, se ainda não estiver instalado.
2. Dê dois cliques em `GERAR_EXE.bat`.
3. O arquivo será criado em:

   `dist\SindromeChatOverlay.exe`

O `.bat` cria um ambiente isolado, instala tudo que é necessário, gera o ícone e executa o PyInstaller. A pasta `dist` será aberta automaticamente quando terminar.

Para enviar a um amigo, envie o `.exe` junto com `LEIA-ME.md`, `LICENSE.txt` e `THIRD_PARTY_NOTICES.md` que estarão na mesma pasta. Cada pessoa pode trocar os próprios canais pelo botão de engrenagem.

### Gerar e baixar pelo GitHub

O projeto inclui `.github/workflows/build-windows.yml`. A ação **Gerar EXE e Release do Windows** compila o programa em uma máquina Windows e publica automaticamente em **Releases**:

- `SindromeChatOverlay.exe`, pronto para executar;
- um `.zip` portátil com o programa e a documentação;
- `SHA256SUMS.txt`, para conferir a integridade dos downloads.

A compilação também fica disponível em **Actions → Gerar EXE e Release do Windows → Artifacts** e pode ser iniciada manualmente por **Run workflow**.

## Como usar

- Arraste a barra superior para mover o overlay.
- Arraste o canto inferior direito para redimensionar.
- Clique na engrenagem para trocar canais e aparência.
- Nas configurações, a rolagem automática e o som podem ser desativados separadamente.
- Clique no cadeado ou pressione `Ctrl + Shift + O` para ativar o clique através.
- Quando estiver bloqueado, use o mesmo atalho ou o ícone ao lado do relógio para desbloquear.
- O botão `⌫` limpa apenas a tela; ele não apaga nada nas plataformas.

Jogos em **janela sem borda** ou **modo janela** são os mais compatíveis. O Windows pode impedir que overlays apareçam sobre alguns jogos em tela cheia exclusiva.

## YouTube: modo automático e API oficial

Por padrão, nenhuma chave é necessária. O aplicativo lê os dados públicos que a própria página do chat utiliza.

Opcionalmente, cada usuário pode informar sua própria chave da **YouTube Data API v3** nas configurações. Nesse caso, o programa usa os endpoints oficiais para ler o chat. Não coloque uma chave pessoal no código nem dentro de um `.exe` que será compartilhado.

Como o modo automático acompanha uma interface pública não documentada do YouTube, uma mudança futura no site pode exigir atualização do aplicativo. O modo oficial é a alternativa mais estável quando uma chave estiver disponível.

## Solução de problemas

### O YouTube fica em “Aguardando a próxima live”

- Confirme que a transmissão está realmente ao vivo e que o chat público está ativado.
- Para uma live não listada, cole o link completo do vídeo nas configurações.
- Lives privadas ou somente para membros exigem autenticação e não são lidas pelo modo público.

### A Twitch não mostra mensagens

- Confirme o nome do canal e se o chat está disponível publicamente.
- Algumas redes corporativas ou antivírus bloqueiam a porta TLS `6697` usada pelo IRC da Twitch.
- Consulte `%APPDATA%\SindromeChatOverlay\overlay.log` para ver o motivo da reconexão.

### O Windows mostra “Windows protegeu o computador”

O `.exe` criado localmente não possui assinatura digital comercial. O SmartScreen pode alertar sobre programas novos. Só execute arquivos que você mesmo compilou ou recebeu de alguém em quem confia.

### O overlay sumiu ou não recebe cliques

- Procure o ícone ao lado do relógio.
- Pressione `Ctrl + Shift + O`.
- As configurações podem ser restauradas removendo `%APPDATA%\SindromeChatOverlay\settings.json` com o aplicativo fechado.

## Desenvolvimento e testes

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python main.py
```

Os provedores de rede rodam em threads separadas; somente a thread principal altera a interface. As requisições usam HTTPS/TLS, limites de tempo e reconexão com espera crescente. Nenhuma chave é escrita no log.

## Referências

O comportamento foi inspirado nos projetos [Transparent Twitch Chat Overlay](https://github.com/baffler/Transparent-Twitch-Chat-Overlay) e [Ghost Chat](https://github.com/Enubia/ghost-chat). O código deste projeto foi implementado separadamente em Python. Veja também `THIRD_PARTY_NOTICES.md`.

## Licença

Código próprio sob licença MIT. As dependências mantêm suas respectivas licenças.
