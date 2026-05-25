"""QAbstractTableModel adapter for catalog rows plus synthetic action column."""

from __future__ import annotations

from typing import Any

from ..qt import QApplication, QAbstractTableModel, QmlNamedElement, QmlUncreatable, QModelIndex, Qt, Slot

QML_IMPORT_NAME = "OpenLogistic.Models"
QML_IMPORT_MAJOR_VERSION = 1
QML_IMPORT_MINOR_VERSION = 0


@QmlNamedElement("CatalogTableModel")
@QmlUncreatable("CatalogTableModel instances are created in Python and injected into QML.")
class CatalogTableModel(QAbstractTableModel):
    _ROW_DATA_ROLE = Qt.ItemDataRole.UserRole + 1
    _COLUMN_KEY_ROLE = Qt.ItemDataRole.UserRole + 2
    _COLUMN_KIND_ROLE = Qt.ItemDataRole.UserRole + 3

    def __init__(self) -> None:
        super().__init__()
        self._rows: list[dict[str, Any]] = []
        self._display_rows: list[tuple[str, ...]] = []
        self._display_column_positions: dict[str, int] = {}
        self._columns: list[dict[str, Any]] = []

    def rowCount(self, parent: QModelIndex | None = None) -> int:
        if parent is not None and parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent: QModelIndex | None = None) -> int:
        if parent is not None and parent.isValid():
            return 0
        return len(self._columns)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if (
            not index.isValid()
            or index.row() < 0
            or index.row() >= len(self._rows)
            or index.column() < 0
            or index.column() >= len(self._columns)
        ):
            return None

        row = self._rows[index.row()]
        column = self._columns[index.column()]
        key = str(column.get("key", ""))
        kind = str(column.get("kind", "data"))

        if role == Qt.ItemDataRole.DisplayRole:
            if kind != "data":
                return ""
            display_column = self._display_column_positions.get(key)
            if display_column is None or index.row() >= len(self._display_rows):
                return ""
            return self._display_rows[index.row()][display_column]
        if role == self._ROW_DATA_ROLE:
            return dict(row)
        if role == self._COLUMN_KEY_ROLE:
            return key
        if role == self._COLUMN_KIND_ROLE:
            return kind
        return None

    def headerData(self, section: int, orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            if 0 <= section < len(self._columns):
                return str(self._columns[section].get("header", ""))
            return None
        if orientation == Qt.Orientation.Vertical:
            return section + 1
        return None

    def roleNames(self) -> dict[int, bytes]:
        return {
            int(Qt.ItemDataRole.DisplayRole): b"display",
            self._ROW_DATA_ROLE: b"rowData",
            self._COLUMN_KEY_ROLE: b"columnKey",
            self._COLUMN_KIND_ROLE: b"columnKind",
        }

    def set_table(
        self,
        rows: list[dict[str, Any]],
        columns: list[dict[str, Any]],
        display_rows: list[tuple[str, ...]],
        display_column_keys: list[str] | tuple[str, ...],
    ) -> None:
        self.beginResetModel()
        try:
            self._rows = [dict(row) for row in rows]
            self._columns = [dict(column) for column in columns]
            self._display_rows = [tuple(display_row) for display_row in display_rows]
            self._display_column_positions = {
                str(column_key): index
                for index, column_key in enumerate(display_column_keys)
            }
        finally:
            self.endResetModel()

    def rows(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self._rows]

    def columns(self) -> list[dict[str, Any]]:
        return [dict(column) for column in self._columns]

    @Slot(int, result=object)
    def row_data(self, row_index: int) -> dict[str, Any]:
        if row_index < 0 or row_index >= len(self._rows):
            return {}
        return dict(self._rows[row_index])

    @Slot(int, result=object)
    def column_data(self, column_index: int) -> dict[str, Any]:
        if column_index < 0 or column_index >= len(self._columns):
            return {}
        return dict(self._columns[column_index])

    @Slot(int, int, result=str)
    def display_data(self, row_index: int, column_index: int) -> str:
        if row_index < 0 or row_index >= len(self._rows):
            return ""
        if column_index < 0 or column_index >= len(self._columns):
            return ""
        column = self._columns[column_index]
        if str(column.get("kind", "data")) != "data":
            return ""
        key = str(column.get("key", ""))
        display_column = self._display_column_positions.get(key)
        if display_column is None or row_index >= len(self._display_rows):
            return ""
        return self._display_rows[row_index][display_column]

    @Slot(int, int, int, int, result=str)
    def display_range_as_tsv(
        self,
        start_row: int,
        start_column: int,
        end_row: int,
        end_column: int,
    ) -> str:
        if not self._rows or not self._columns:
            return ""

        first_row = max(0, min(int(start_row), int(end_row)))
        last_row = min(len(self._rows) - 1, max(int(start_row), int(end_row)))
        first_column = max(0, min(int(start_column), int(end_column)))
        last_column = min(len(self._columns) - 1, max(int(start_column), int(end_column)))

        data_columns = [
            column_index
            for column_index in range(first_column, last_column + 1)
            if str(self._columns[column_index].get("kind", "data")) == "data"
        ]
        if first_row > last_row or not data_columns:
            return ""

        lines: list[str] = []
        for row_index in range(first_row, last_row + 1):
            values = [
                self._sanitize_tsv_cell(self.display_data(row_index, column_index))
                for column_index in data_columns
            ]
            lines.append("\t".join(values))
        return "\n".join(lines)

    @Slot(int, int, int, int, result=bool)
    def copy_display_range_to_clipboard(
        self,
        start_row: int,
        start_column: int,
        end_row: int,
        end_column: int,
    ) -> bool:
        text = self.display_range_as_tsv(start_row, start_column, end_row, end_column)
        if text == "":
            return False
        clipboard = QApplication.clipboard()
        if clipboard is None:
            return False
        clipboard.setText(text)
        return True

    @staticmethod
    def _sanitize_tsv_cell(value: str) -> str:
        return str(value).replace("\t", " ").replace("\r", " ").replace("\n", " ")
