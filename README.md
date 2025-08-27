# <img width="49" height="35" alt="image" src="https://github.com/user-attachments/assets/ca0cd328-5ca6-4be8-97da-4033aa69d1f9" /> CapTube

**CapTube**, é um aplicativo simples e eficiente, para download de vídeos e áudios diretamente do YouTube, desenvolvido em **Python + PyQt5**.

O CapTube combina interface amigável, usabilidade prática e design minimalista, para facilitar a vida de quem deseja baixar conteúdos da plataforma.

Especialmente, para usuários que necessitam de vídeos para fazer cortes, ou baixar somente áudios. Apesar de existir sites que fazem isso, a vantagem é não ter propagandas no CapTube. E você pode personalizá-lo como quiser diretamente no código-fonte. 😉👨‍💻

## ✨ Funcionalidades

- ✅ Baixar vídeos do YouTube em formato MP4
- ✅ Baixar apenas o áudio em formato MP3
- ✅ Botão para colar automaticamente links da área de transferência
- ✅ Botão para limpar rapidamente o campo de URL
- ✅ Escolha e abertura automática da pasta de downloads
- ✅ Interface moderna com efeitos de hover nos botões
- ✅ Saída em pasta própria (/downloads) gerenciada pelo app
- ✅ Aplicativo já compilado em .exe (Windows) para uso imediato

## 🖼️ Interface

O layout foi desenvolvido em PyQt5, com foco em:

- Design limpo e intuitivo
- Botões estilizados com efeitos de hover (verde, vermelho, azul pastel e amarelo)
- Campos bem organizados e responsivos dentro da janela

<img width="680" height="393" alt="image" src="https://github.com/user-attachments/assets/8f4313ea-b609-45fd-b204-2fa9c66472af" />


## 🛠️ Tecnologias Utilizadas

- Python 3.11.9
- PyQt5 – Interface gráfica
- pytube – Download de vídeos do YouTube
- PyInstaller – Empacotamento do app em .exe
- Qt Designer – Criação do layout visual

## 📂 Estrutura do Projeto
- CAPTUBE/
- │── build/_______________# Arquivos gerados pelo PyInstaller
- │''''''└── captube/
- │── dist/________________# Arquivos finais (.exe + pasta downloads)
- │''''''├── downloads/
- │''''''└── captube.exe
- │── icons/_______________# Ícones do projeto
- │── captube.py__________# Código principal do aplicativo
- │── captube.spec________# Arquivo de build do PyInstaller

## 🚀 Como Executar
🔹 Opção 1 – Executar o código-fonte (bash)

1. Clone este repositório:
```bash
git clone https://github.com/alexssmenezes/captube.git
cd captube
```

2. Criar e ativar um ambiente virtual (opcional, mas recomendado):
```bash
python -m venv venv
# Ativar ambiente virtual:
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

3. Instale as dependências:
```bash
pip install -r requirements.txt
```

4. Execute o aplicativo:
```bash
python captube.py
```

5. Empacotando em Executável (.exe):
- Obs.: Caso queira gerar seu próprio .exe (Windows), utilize:
```bash
pyinstaller --onefile --noconsole --icon=icons/app.ico captube.py
```

🔹Opção 2 – Usar versão compilada (.exe)

- Baixe o arquivo captube.exe na pasta dist/.
- Dê duplo clique e utilize o app sem precisar instalar nada.

## 📖 Usabilidade

- Abra o aplicativo CapTube
- Cole ou digite o link de um vídeo do YouTube
- Escolha se deseja baixar o vídeo, áudio ou vídeo sem o áudio
- Defina a pasta de saída (ou use a padrão downloads)
- Clique no botão correspondente e aguarde a conclusão
- O arquivo será salvo na pasta downloads/ ou na que você escolheu

## 💡 Futuras Melhorias

- ✅ Barra de progresso para exibir status do download
- ✅ Suporte a playlists inteiras
- ⌛ Opção para escolher qualidade do vídeo
- ⌛ Versão PWA para uso direto no navegador

## 👨‍💻 Autor

Projeto desenvolvido por Alex Menezes.
- 📌 Contato: [GitHub](https://github.com/alexssmenezes)
- 📌 Contato: [LinkedIn](https://www.linkedin.com/in/alexssmenezes)

## 📃 Licença

- Este projeto está licenciado sob os termos da [Licença MIT](LICENSE).
- Copyright © 2025 CapTube - YouTube Downloader by Alex Menezes. Todos os direitos reservados.
