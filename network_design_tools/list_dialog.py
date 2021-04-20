import os
from PyQt5 import uic
from PyQt5.QtWidgets import QDialog

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
Ui_ListDialog, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), 'list_dialog_base.ui'))

class ListDialog(QDialog, Ui_ListDialog):

    def __init__(self, parent=None):
        """Constructor."""
        super(ListDialog, self).__init__(parent)
        # Set up the user interface from Designer through Ui_Dialog.
        self.setupUi(self)

    def getSelectedValue(self):
        selectedItems = self.listWidget.selectedItems()
        if len(selectedItems) == 1:
            return selectedItems[0].text()
        else:
            return None

    def setValues(self, helpText, listItems):
        self.lblHeading.setText(helpText)
        self.listWidget.clear()
        self.listWidget.addItems(listItems)
        if self.listWidget.count() > 0:
            self.listWidget.setCurrentItem(self.listWidget.item(0))
            self.listWidget.setFocus()
