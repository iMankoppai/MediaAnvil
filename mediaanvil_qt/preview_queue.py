"""PreviewQueueMixin: behavior using the state and controls owned by PreviewPage."""
from pathlib import Path
import random
QUEUE_TAB = 1


class PreviewQueueMixin:
    def refresh_queue_list(self):
        """Mirror the queue model into the visible list.

        The row signal is blocked while the list is rebuilt: setting the current
        row would otherwise run the row handler, which loads the file a second
        time and restarts playback from the beginning.
        """
        tracks=self.queue_tracks
        self.queue.blockSignals(True)
        try:
            self.queue.clear()
            if tracks.entries:
                self.queue.add_paths(tracks.entries)
            if tracks.index>=0:
                self.queue.setCurrentRow(tracks.index)
        finally:
            self.queue.blockSignals(False)
        self.queue_button.setText(self.app.t(f'队列 ({len(tracks)})'))
        self.queue_tab_label()

    def queue_tab_label(self):
        """Keep the queue count on the tab, in either language.

        The count is a suffix rather than part of the label so that translating
        the label cannot drop it.
        """
        count=len(self.queue_tracks)
        self.tabs.set_suffix(f'({count})' if count else '')

    def show_queue(self):
        self.tabs.set_current_index(QUEUE_TAB)

    def clear_queue(self):
        """Empty the queue and stop playback, since nothing is selected."""
        self.queue_tracks.clear()
        self.queue.blockSignals(True);self.queue.clear();self.queue.blockSignals(False)
        self.close_current_player()
        self.path=None
        self.queue_button.setText(self.app.t('队列 (0)'))
        self.queue_tab_label()
        self.state_line.setText('等待载入音频')
        self.title.setText('尚未选择音频');self.info.setText('选择一首音频，开始聆听')
        self.file_path.clear();self.resume_row.hide()
        self.timeline=();self.refill_lyrics();self.notice(self.app.t('等待载入音频'))

    def queue_changed(self):
        """Re-sync the model after the list is reordered or edited by dragging."""
        self.queue_tracks.entries=[Path(p) for p in self.queue.paths()]
        self.queue_tracks.index=self.queue.currentRow()
        self.refresh_last_position()

    def queue_row_changed(self,row):
        if row<0 or row>=len(self.queue_tracks):return
        if self.queue_tracks.index==row and self.path:return
        self.queue_tracks.select(row)
        self.load(self.queue_tracks.current)

    def toggle_shuffle(self):
        from core.play_queue import ORDER_IN_ORDER,ORDER_SHUFFLE
        shuffle=self.queue_tracks.order!=ORDER_SHUFFLE
        self.queue_tracks.set_order(ORDER_SHUFFLE if shuffle else ORDER_IN_ORDER,
                                    shuffle_seed=random.randrange(1<<30))
        self.notice(self.app.t('已开启随机播放' if shuffle else '已关闭随机播放'))
        self.state_line.setText(self.state_text())

    def pick_next(self,automatic=True):
        """The next file for the current repeat mode, or None when playback stops."""
        if automatic and not self.auto_next.isChecked():
            return None
        return self.queue_tracks.advance(mode=self.repeat.currentData(),automatic=automatic)

    def play_next(self,automatic=True):
        target=self.pick_next(automatic=automatic)
        if target is None:
            if automatic:self.notice(self.app.t('播放列表已结束'))
            return False
        self.refresh_queue_list()
        self.load(target)
        return True

    def play_previous(self):
        target=self.queue_tracks.rewind()
        if target is None:return False
        self.refresh_queue_list()
        self.load(target)
        return True

