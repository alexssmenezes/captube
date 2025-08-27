import sys
import os
import re
import time
import threading
from pathlib import Path

from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QHBoxLayout, QRadioButton, QMessageBox,
    QProgressBar, QFileDialog
)

# Use pytubefix para maior resiliência a mudanças do YouTube
from pytubefix import YouTube, Playlist


# -------------------------
# Utilitários de caminho/recursos
# -------------------------
def resource_path(relative_path: str) -> str:
    """
    Retorna o caminho absoluto de um recurso, funcionando
    tanto no ambiente de desenvolvimento quanto no executável (PyInstaller).
    """
    try:
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def set_hover_icon(button: QPushButton, normal_icon: str, hover_icon: str) -> None:
    """
    Define ícones para estado normal e hover. Se o arquivo não existir,
    o botão fica sem ícone (não quebra a UI).
    """
    normal = resource_path(normal_icon)
    hover = resource_path(hover_icon)
    button.normal_icon = QIcon(normal) if os.path.exists(normal) else QIcon()
    button.hover_icon = QIcon(hover) if os.path.exists(hover) else QIcon()
    button.setIcon(button.normal_icon)

    def on_enter(event):
        button.setIcon(button.hover_icon)
        QWidget.enterEvent(button, event)

    def on_leave(event):
        button.setIcon(button.normal_icon)
        QWidget.leaveEvent(button, event)

    button.enterEvent = on_enter
    button.leaveEvent = on_leave


def sanitize_filename(name: str) -> str:
    """
    Remove/normaliza caracteres inválidos para nomes de arquivos.
    """
    name = name.strip()
    name = re.sub(r"[\\/:*?\"<>|]", "_", name)
    name = re.sub(r"\s+", " ", name)
    return name[:180]  # evita nomes gigantes


def unique_path(dest_dir: Path, base_name: str, ext: str) -> Path:
    """
    Gera um caminho único evitando sobrescrever arquivos existentes.
    """
    candidate = dest_dir / f"{base_name}.{ext}"
    idx = 1
    while candidate.exists():
        candidate = dest_dir / f"{base_name} ({idx}).{ext}"
        idx += 1
    return candidate


# -------------------------
# Worker de download em thread separada
# -------------------------
class DownloadWorker(QThread):
    # Sinais para UI
    progress = pyqtSignal(int)                 # progresso do item atual (0-100)
    status = pyqtSignal(str)                   # mensagens de status
    finished_ok = pyqtSignal()                 # finalizou tudo com sucesso
    finished_with_cancel = pyqtSignal()        # cancelado
    error = pyqtSignal(str)                    # erro fatal
    item_done = pyqtSignal(str, str)           # (titulo, caminho) por item concluído

    def __init__(self, url: str, dest_dir: Path, mode: str):
        super().__init__()
        self.url = url
        self.dest_dir = dest_dir
        self.mode = mode  # 'full' | 'audio' | 'video_only'
        self.pause_event = threading.Event()   # quando set() -> PAUSADO
        self.cancel_event = threading.Event()
        self._current_total = None

    def cancel(self):
        """Sinaliza cancelamento cooperativo."""
        self.cancel_event.set()

    def toggle_pause(self):
        """Alterna estado de pausa (cooperativo)."""
        if self.pause_event.is_set():
            self.pause_event.clear()
        else:
            self.pause_event.set()

    # Callback do pytube (rodará dentro desta thread)
    def _on_progress(self, stream, chunk, bytes_remaining):
        # Pausa cooperativa
        while self.pause_event.is_set():
            if self.cancel_event.is_set():
                raise Exception("Cancelado durante pausa.")
            time.sleep(0.1)
        if self.cancel_event.is_set():
            raise Exception("Cancelado pelo usuário.")

        total = self._current_total or getattr(stream, "filesize", None) or getattr(stream, "filesize_approx", None)
        if not total:
            return
        done = total - bytes_remaining
        pct = int(max(0, min(100, (done / total) * 100)))
        self.progress.emit(pct)

    def _select_stream(self, yt: YouTube):
        """
        Seleciona o stream de acordo com o modo.
        'full' => tenta progressivo MP4 (vídeo+áudio)
        'audio' => apenas áudio (maior bitrate)
        'video_only' => apenas vídeo (maior resolução)
        """
        try:
            if self.mode == "full":
                # Tenta o melhor progressivo MP4
                stream = (
                    yt.streams.filter(progressive=True, file_extension="mp4")
                    .order_by("resolution")
                    .desc()
                    .first()
                )
                if stream is None:
                    # Último recurso: qualquer progressivo
                    stream = (
                        yt.streams.filter(progressive=True)
                        .order_by("resolution")
                        .desc()
                        .first()
                    )
                return stream

            if self.mode == "audio":
                stream = (
                    yt.streams.filter(only_audio=True)
                    .order_by("abr")
                    .desc()
                    .first()
                )
                return stream

            if self.mode == "video_only":
                stream = (
                    yt.streams.filter(only_video=True)
                    .order_by("resolution")
                    .desc()
                    .first()
                )
                return stream
        except Exception:
            return None

        return None

    def _download_one(self, link: str):
        """
        Faz download de um único link, emitindo sinais conforme o progresso.
        """
        # Pode lançar exceção que será capturada no run()
        yt = YouTube(link, on_progress_callback=self._on_progress)
        title = sanitize_filename(yt.title or "video")
        stream = self._select_stream(yt)

        if stream is None:
            raise Exception("Não foi possível encontrar um stream compatível para esse modo.")

        # Descobrir extensão correta
        ext = getattr(stream, "subtype", None)
        if not ext:
            mime = getattr(stream, "mime_type", "")  # ex: "video/mp4"
            ext = mime.split("/")[-1] if "/" in mime else "mp4"

        # Tamanho total para cálculo do progresso
        self._current_total = getattr(stream, "filesize", None) or getattr(stream, "filesize_approx", None)

        # Caminho de saída único
        out_path = unique_path(self.dest_dir, title, ext)

        self.status.emit(f"Iniciando: {yt.title}")
        # stream.download aceita output_path e filename (já garantimos unique_path)
        stream.download(output_path=str(self.dest_dir), filename=out_path.name)

        # Ao terminar o item
        self.progress.emit(100)
        self.item_done.emit(yt.title or title, str(out_path))

    def _iter_playlist(self, p: Playlist):
        """
        Itera a playlist baixando item por item, respeitando cancel/pause.
        """
        count = 0
        total_items = len(p.video_urls) if hasattr(p, "video_urls") else 0
        for url in p.video_urls:
            count += 1
            if self.cancel_event.is_set():
                break
            self.status.emit(f"Baixando item {count}/{total_items}")
            self._download_one(url)

    def run(self):
        """
        Execução principal do worker na thread.
        """
        try:
            self.dest_dir.mkdir(parents=True, exist_ok=True)

            # Tenta identificar playlist (Playlist pode lançar)
            is_playlist = False
            p = None
            try:
                p = Playlist(self.url)
                if hasattr(p, "video_urls") and len(p.video_urls) > 0:
                    is_playlist = True
            except Exception:
                is_playlist = False
                p = None  # type: ignore

            if is_playlist and p is not None:
                self.status.emit("Detectada playlist. Preparando itens...")
                self._iter_playlist(p)
            else:
                self._download_one(self.url)

            if self.cancel_event.is_set():
                self.finished_with_cancel.emit()
            else:
                self.finished_ok.emit()

        except Exception as e:
            # Propaga mensagem de erro para UI
            self.error.emit(str(e))


# -------------------------
# Janela principal
# -------------------------
class YouTubeDownloader(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CapTube - YouTube Downloader")
        self.setGeometry(200, 200, 680, 360)
        self.setWindowFlag(Qt.WindowMinimizeButtonHint, True)
        self.setWindowFlag(Qt.WindowCloseButtonHint, True)
        self.setWindowIcon(QIcon(resource_path("icons/icon.ico")))

        # Estado
        self.worker = None  # type: ignore
        self.is_downloading = False

        # URL
        self.url_label = QLabel("Insira o link do vídeo ou playlist:")
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Cole o link aqui...")

        self.paste_btn = QPushButton("Colar")
        self.paste_btn.clicked.connect(self.paste_link)

        self.clear_btn = QPushButton("Limpar")
        self.clear_btn.clicked.connect(self.clear_link)

        url_hbox = QHBoxLayout()
        url_hbox.addWidget(self.url_input)
        url_hbox.addWidget(self.paste_btn)
        url_hbox.addWidget(self.clear_btn)

        # Opções
        self.video_radio = QRadioButton("Baixar vídeo completo")
        self.audio_radio = QRadioButton("Baixar apenas áudio")
        self.video_only_radio = QRadioButton("Baixar apenas vídeo (sem áudio)")
        self.video_radio.setChecked(True)

        # Progresso
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setAlignment(Qt.AlignCenter)
        self.progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid #CCCCCC;
                border-radius: 6px;
                text-align: center;
                height: 22px;
            }
            QProgressBar::chunk {
                border-radius: 6px;
                background-color: #4CAF50;
            }
        """)

        # Status label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #555;")

        # Botões
        self.download_btn = QPushButton(" Baixar")
        self.download_btn.clicked.connect(self.download_content)
        set_hover_icon(self.download_btn, "icons/download_black.png", "icons/download_black.png")

        self.folder_btn = QPushButton(" Escolher Pasta")
        self.folder_btn.clicked.connect(self.choose_folder)
        set_hover_icon(self.folder_btn, "icons/folder_black.png", "icons/folder_black.png")

        self.pause_btn = QPushButton(" Pause")
        self.pause_btn.clicked.connect(self.toggle_pause)
        set_hover_icon(self.pause_btn, "icons/pause.png", "icons/pause.png")
        self.pause_btn.setEnabled(False)

        self.cancel_btn = QPushButton(" Cancelar")
        self.cancel_btn.clicked.connect(self.cancel_download)
        set_hover_icon(self.cancel_btn, "icons/cancel.png", "icons/cancel.png")
        self.cancel_btn.setEnabled(False)

        # ---------- estilos dos botões (mantendo aparência original) ----------
        common_btn_style = """
            QPushButton {
                background-color: #E0E0E0;
                border-radius: 6px;
                padding: 8px 10px;
            }
        """
        self.download_btn.setStyleSheet(common_btn_style + "QPushButton:hover { background-color: #80EF80; color: #000; }")
        self.folder_btn.setStyleSheet(common_btn_style + "QPushButton:hover { background-color: #DFD880; color: #000; }")
        self.pause_btn.setStyleSheet(common_btn_style + "QPushButton:hover { background-color: #ADD8E6; color: #000; }")
        self.cancel_btn.setStyleSheet(common_btn_style + "QPushButton:hover { background-color: #FF746C; color: #FFF; }")
        self.paste_btn.setStyleSheet("QPushButton:hover { background-color: #ADD8E6; border-radius: 6px; color: #000; }")
        self.clear_btn.setStyleSheet("QPushButton:hover { background-color: #ADD8E6; border-radius: 6px; color: #000; }")

        # -------------------------
        # Layout principal (mantido)
        # -------------------------
        vbox = QVBoxLayout()
        vbox.addWidget(self.url_label)
        vbox.addLayout(url_hbox)
        vbox.addWidget(self.video_radio)
        vbox.addWidget(self.audio_radio)
        vbox.addWidget(self.video_only_radio)
        vbox.addWidget(self.progress)
        vbox.addWidget(self.status_label)

        # Botões de ação (mantidos na mesma ordem/layout)
        hbox = QHBoxLayout()
        hbox.addWidget(self.download_btn)
        hbox.addWidget(self.folder_btn)
        hbox.addWidget(self.pause_btn)
        hbox.addWidget(self.cancel_btn)
        vbox.addLayout(hbox)

        # Rodapé (igual ao original)
        footer = QLabel("Copyright © 2025 CapTube Alex Menezes. Todos os direitos reservados.")
        footer.setAlignment(Qt.AlignCenter)
        footer.setStyleSheet("color: gray; font-size: 10px; margin-top: 10px;")
        vbox.addWidget(footer)

        self.setLayout(vbox)

        # Pasta padrão
        self.destino = Path("downloads")
        self.destino.mkdir(exist_ok=True)

        # Efeito de brilho no progresso
        self.timer_brilho = None
        self.intensidade = 0
        self.subindo = True

    # -------------------------
    # reset UI (não altera layout) — reseta estados e controles
    # -------------------------
    def reset_ui(self):
        """Restaura todos os campos e controles para o estado inicial (sem recriar layout)."""
        self.url_input.clear()
        self.video_radio.setChecked(True)
        self.progress.setValue(0)
        self.status_label.setText("")
        self.pause_btn.setText(" Pause")
        # garante botoes desativados
        self.pause_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        # habilita controles de edição
        self._lock_ui(False)
        self.parar_brilho()

    # -------------------------
    # Efeitos visuais
    # -------------------------
    def iniciar_brilho(self):
        """Inicia efeito pulsante (brilho) da barra de progresso."""
        if self.timer_brilho:
            return

        def pulsar():
            self.intensidade += 5 if self.subindo else -5
            if self.intensidade >= 100:
                self.subindo = False
            elif self.intensidade <= 0:
                self.subindo = True
            r, g, b = (76, 175, 80)
            g_mod = min(255, g + int(self.intensidade * 0.5))
            self.progress.setStyleSheet(f"""
                QProgressBar {{
                    border: 1px solid #CCCCCC;
                    border-radius: 6px;
                    text-align: center;
                    height: 22px;
                }}
                QProgressBar::chunk {{
                    border-radius: 6px;
                    background-color: rgb({r}, {g_mod}, {b});
                }}
            """)

        self.timer_brilho = QTimer(self)
        self.timer_brilho.timeout.connect(pulsar)
        self.timer_brilho.start(50)

    def parar_brilho(self):
        """Para o brilho e reseta estilo padrão da barra."""
        if self.timer_brilho:
            self.timer_brilho.stop()
            self.timer_brilho.deleteLater()
            self.timer_brilho = None
        # reset estilo
        self.progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid #CCCCCC;
                border-radius: 6px;
                text-align: center;
                height: 22px;
            }
            QProgressBar::chunk {
                border-radius: 6px;
                background-color: #4CAF50;
            }
        """)

    # -------------------------
    # Ações UI
    # -------------------------
    def paste_link(self):
        """Cola o link do clipboard no campo de texto."""
        cb = QApplication.clipboard()
        text = cb.text().strip()
        if text:
            self.url_input.setText(text)

    def clear_link(self):
        """Limpa o formulário (reseta UI)."""
        self.reset_ui()

    def choose_folder(self):
        """Abre diálogo para escolher pasta de destino."""
        folder = QFileDialog.getExistingDirectory(self, "Escolher pasta de destino", str(self.destino.resolve()))
        if folder:
            self.destino = Path(folder)
            self.status_label.setText(f"Pasta de destino: {self.destino}")

    def _current_mode(self) -> str:
        """Retorna o modo atual selecionado (full | audio | video_only)."""
        if self.audio_radio.isChecked():
            return "audio"
        if self.video_only_radio.isChecked():
            return "video_only"
        return "full"

    def _lock_ui(self, downloading: bool):
        """
        Bloqueia/desbloqueia elementos da UI durante o download.
        Mantém layout e estilos originais.
        """
        self.is_downloading = downloading
        self.download_btn.setEnabled(not downloading)
        self.folder_btn.setEnabled(not downloading)
        self.paste_btn.setEnabled(not downloading)
        self.clear_btn.setEnabled(not downloading)
        self.url_input.setEnabled(not downloading)
        # pause/cancel são habilitados apenas quando há download
        self.pause_btn.setEnabled(downloading)
        self.cancel_btn.setEnabled(downloading)

    def download_content(self):
        """Inicializa o worker de download e conecta sinais."""
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.information(self, "Atenção", "Por favor, insira um link.")
            return

        mode = self._current_mode()
        self.progress.setValue(0)
        self.status_label.setText("Preparando download...")
        self._lock_ui(True)
        self.iniciar_brilho()

        # garante flags
        self.pause_btn.setText(" Pause")
        self.pause_btn.setEnabled(True)
        self.cancel_btn.setEnabled(True)

        # cria worker e conecta sinais
        self.worker = DownloadWorker(url, self.destino, mode)
        self.worker.progress.connect(self.on_progress)
        self.worker.status.connect(self.on_status)
        self.worker.item_done.connect(self.on_item_done)
        self.worker.error.connect(self.on_error)
        self.worker.finished_ok.connect(self.on_finished_ok)
        self.worker.finished_with_cancel.connect(self.on_finished_cancel)

        # start da thread
        self.worker.start()

    def toggle_pause(self):
        """Alterna pausa/resume — controla o evento de pausa do worker."""
        if not self.worker:
            QMessageBox.information(self, "Atenção", "Não há download em andamento.")
            return
        self.worker.toggle_pause()
        # mostra status e atualiza texto do botão
        if self.worker.pause_event.is_set():
            self.status_label.setText("Pausado")
            self.pause_btn.setText(" Resume")
        else:
            self.status_label.setText("Retomando...")
            self.pause_btn.setText(" Pause")

    def cancel_download(self):
        """Cancela o download em andamento (sinaliza o worker)."""
        if not self.worker or not self.is_downloading:
            QMessageBox.information(self, "Atenção", "Nenhum download para cancelar.")
            return
        # sinaliza cancelamento cooperativo
        self.worker.cancel()
        self.status_label.setText("Cancelando...")

    # -------------------------
    # Slots de sinais do Worker
    # -------------------------
    def on_progress(self, value: int):
        """Atualiza barra de progresso (0-100)."""
        # protege valores inválidos
        try:
            v = int(value)
        except Exception:
            return
        self.progress.setValue(max(0, min(100, v)))

    def on_status(self, msg: str):
        """Atualiza label de status com mensagem do worker."""
        if msg is None:
            msg = ""
        self.status_label.setText(msg)

    def on_item_done(self, title: str, path: str):
        """Indica que um item foi concluído (playlist ou single)."""
        # Mensagem discreta a cada item concluído
        display_title = title or "item"
        self.status_label.setText(f"Concluído: {display_title}\nSalvo em: {path}")

    def on_error(self, msg: str):
        """Tratamento centralizado de erro fatal do worker."""
        self._lock_ui(False)
        self.parar_brilho()
        self.progress.setValue(0)
        self.pause_btn.setText(" Pause")
        QMessageBox.critical(self, "Erro", f"Ocorreu um erro:\n{msg}")

    def on_finished_ok(self):
        """Finalização com sucesso: libera UI e notifica usuário."""
        self._lock_ui(False)
        self.parar_brilho()
        self.pause_btn.setText(" Pause")
        self.status_label.setText("Todos os downloads concluídos.")
        QMessageBox.information(self, "Concluído", "Download finalizado com sucesso!")
        # Agendar o reset da interface para logo depois de fechar a mensagem
        QTimer.singleShot(0, self.reset_ui)

    def on_finished_cancel(self):
        """Finalização por cancelamento: limpa e notifica."""
        self._lock_ui(False)
        self.parar_brilho()
        self.progress.setValue(0)
        self.pause_btn.setText(" Pause")
        self.status_label.setText("Download cancelado.")
        QMessageBox.information(self, "Cancelado", "O download foi cancelado.")

# -------------------------
# Execução
# -------------------------
def main():
    app = QApplication(sys.argv)
    win = YouTubeDownloader()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
