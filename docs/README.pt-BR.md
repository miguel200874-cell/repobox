# Repo2Box

**Transforme um repositório em uma imagem inicializável para Raspberry Pi.**

O Repo2Box analisa um projeto Python ou Node.js, cria um manifesto revisável e
gera uma imagem inicializável para Pi 4 ou Pi 5 com o Raspberry Pi OS, as
dependências e a aplicação configurada para iniciar automaticamente.

```bash
repobox image https://github.com/voce/seu-projeto \
  --target pi5 \
  --engine-dir ./rpi-image-gen
```

## Gerar a imagem completa

No Windows ou macOS, publique o projeto e abra no GitHub:

**Actions → Build Raspberry Pi image → Run workflow**

Escolha `pi4` ou `pi5`. Ao terminar, baixe o artefato `.img.xz` e selecione
**Use custom** no Raspberry Pi Imager. O arquivo já contém o sistema e a
aplicação; nessa instalação inicial não é necessário enviar o projeto por SSH.

Em Linux, a imagem também pode ser compilada localmente:

```bash
git clone --branch v2.7.0 --depth 1 \
  https://github.com/raspberrypi/rpi-image-gen.git
sudo ./rpi-image-gen/install_deps.sh

repobox image examples/hello-python \
  --target pi5 \
  --hostname repobox \
  --ssh-public-key ~/.ssh/id_ed25519.pub \
  --engine-dir ./rpi-image-gen
```

A chave pública é opcional. Sem ela, o login permanece bloqueado e a aplicação
continua iniciando normalmente. Com ela, o acesso do usuário `pi` funciona
somente por chave; o Repo2Box rejeita chaves privadas.

Para apenas preparar e inspecionar a configuração em qualquer sistema:

```bash
repobox image examples/hello-python --target pi5 --prepare-only
```

## Instalação para desenvolvimento

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
repobox doctor
```

No PowerShell, use `.venv\Scripts\Activate.ps1`.

## Teste rápido

```bash
repobox analyze examples/hello-python --output demo.toml --force
repobox build examples/hello-python --target pi5 --output-dir dist
repobox inspect dist/repo2box-hello-pi5-arm64.rbx.tar.gz
```

## Atualizar um Raspberry já instalado

```bash
repobox deploy examples/hello-python \
  --target pi5 \
  --host pi@raspberrypi.local
```

Depois, acesse `http://raspberrypi.local:8080`. O SSH é a rota rápida de
atualização; não é obrigatório para iniciar usando a imagem completa.

Antes de conectar, confira os comandos:

```bash
repobox deploy examples/hello-python \
  --target pi5 \
  --host pi@raspberrypi.local \
  --dry-run
```

## Segurança

O Repo2Box executa código do repositório. Use apenas fontes confiáveis. Arquivos
`.env`, chaves privadas, links simbólicos e pastas de dependências são excluídos
por padrão, mas isso não substitui uma auditoria do código.

O núcleo é gratuito e funciona sem cadastro ou banco de dados. Uma futura
plataforma paga poderá oferecer builds na nuvem, repositórios privados,
atualizações e gerenciamento de dispositivos.
