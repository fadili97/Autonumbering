import os.path

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QDockWidget, QPushButton, QVBoxLayout, QWidget, QMessageBox
from qgis.core import QgsProject, QgsVectorLayer, edit, QgsWkbTypes, QgsField, Qgis
from qgis.PyQt.QtCore import QVariant

class AutoNumbering:
    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        
        # Initialize plugin state
        self.actions = []
        self.menu = 'Auto Numbering'
        self.toolbar = self.iface.addToolBar('Auto Numbering')
        self.toolbar.setObjectName('AutoNumbering')
        
        # Plugin-specific initialization
        self.dock_widget = None
        self.layer = None
        self.field_name = "number"
        self.history = []
        self.active = False

    def add_action(self, icon_path, text, callback, enabled_flag=True,
                  checkable=False, add_to_menu=True, add_to_toolbar=True,
                  status_tip=None, whats_this=None, parent=None):
        
        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)
        action.setCheckable(checkable)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToMenu(self.menu, action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""
        
        # Create toggle action
        icon_path = os.path.join(self.plugin_dir, 'icon.png')
        self.toggle_action = self.add_action(
            icon_path,
            text='Toggle Auto Numbering',
            callback=self.toggle_numbering,
            parent=self.iface.mainWindow(),
            checkable=True)

        # Create dock widget
        self.dock_widget = QDockWidget("Auto Numbering Controls", self.iface.mainWindow())
        self.dock_widget.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        
        # Create widget for dock
        dock_content = QWidget()
        layout = QVBoxLayout()
        
        # Add control buttons
        self.undo_btn = QPushButton("Undo Last Number")
        self.undo_btn.clicked.connect(self.undo_last)
        self.undo_btn.setEnabled(False)
        
        self.reset_btn = QPushButton("Reset All Numbers")
        self.reset_btn.clicked.connect(self.reset_numbers)
        
        self.restart_btn = QPushButton("Restart from 1")
        self.restart_btn.clicked.connect(self.restart_numbering)
        
        # Add buttons to layout
        layout.addWidget(self.undo_btn)
        layout.addWidget(self.reset_btn)
        layout.addWidget(self.restart_btn)
        layout.addStretch()
        
        dock_content.setLayout(layout)
        self.dock_widget.setWidget(dock_content)
        
        # Add dock widget to QGIS
        self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dock_widget)
        self.dock_widget.hide()

    def toggle_numbering(self, checked):
        if checked:
            self.start_numbering()
        else:
            self.stop_numbering()

    def start_numbering(self):
        self.layer = self.iface.activeLayer()
        
        if not self.layer:
            self.show_warning("Please select a layer first!")
            self.toggle_action.setChecked(False)
            return
            
        if self.layer.geometryType() != QgsWkbTypes.PolygonGeometry:
            self.show_warning("Please select a polygon layer!")
            self.toggle_action.setChecked(False)
            return
        
        # Check/create number field
        field_idx = self.layer.fields().indexOf(self.field_name)
        if field_idx == -1:
            self.layer.startEditing()
            provider = self.layer.dataProvider()
            provider.addAttributes([QgsField(self.field_name, QVariant.Int)])
            self.layer.updateFields()
            self.layer.commitChanges()
        
        # Connect selection signal
        self.layer.selectionChanged.connect(self.number_selected)
        self.active = True
        self.dock_widget.show()
        
        self.iface.messageBar().pushMessage(
            "Auto Numbering",
            "Auto numbering activated! Select polygons to number them.",
            level=Qgis.Info,
            duration=5
        )

    def stop_numbering(self):
        if self.layer:
            try:
                self.layer.selectionChanged.disconnect(self.number_selected)
            except:
                pass
        self.active = False
        self.dock_widget.hide()

    def number_selected(self):
        if not self.active:
            return
            
        selected_features = self.layer.selectedFeatures()
        if not selected_features or len(selected_features) > 1:
            return
            
        feature = selected_features[0]
        field_idx = self.layer.fields().indexOf(self.field_name)
        
        # Skip if already numbered
        if feature[self.field_name] is not None and feature[self.field_name] > 0:
            return
        
        # Find next number
        max_number = 0
        for feat in self.layer.getFeatures():
            if feat[self.field_name] is not None and feat[self.field_name] > max_number:
                max_number = feat[self.field_name]
        next_number = max_number + 1
        
        # Save for undo
        self.history.append({
            'feature_id': feature.id(),
            'old_value': feature[self.field_name],
            'new_value': next_number
        })
        
        # Update value
        self.layer.startEditing()
        success = self.layer.changeAttributeValue(
            feature.id(),
            field_idx,
            next_number
        )
        self.layer.commitChanges()
        
        if success:
            self.iface.messageBar().pushMessage(
                "Success",
                f"Number {next_number} assigned",
                level=Qgis.Success,
                duration=3
            )
            self.undo_btn.setEnabled(True)

    def undo_last(self):
        if not self.history:
            return
            
        last_action = self.history.pop()
        field_idx = self.layer.fields().indexOf(self.field_name)
        
        self.layer.startEditing()
        success = self.layer.changeAttributeValue(
            last_action['feature_id'],
            field_idx,
            last_action['old_value']
        )
        self.layer.commitChanges()
        
        if success:
            self.iface.messageBar().pushMessage(
                "Undo",
                f"Removed number {last_action['new_value']}",
                level=Qgis.Info,
                duration=3
            )
            
        if not self.history:
            self.undo_btn.setEnabled(False)

    def reset_numbers(self):
        if not self.layer:
            return
            
        reply = QMessageBox.question(
            self.iface.mainWindow(),
            'Reset Numbers',
            'Are you sure you want to reset all numbers?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            field_idx = self.layer.fields().indexOf(self.field_name)
            self.layer.startEditing()
            
            for feature in self.layer.getFeatures():
                self.layer.changeAttributeValue(
                    feature.id(),
                    field_idx,
                    None
                )
                
            self.layer.commitChanges()
            self.history.clear()
            self.undo_btn.setEnabled(False)

    def restart_numbering(self):
        if not self.layer:
            return
            
        field_idx = self.layer.fields().indexOf(self.field_name)
        
        # Find all numbered features
        numbered_features = []
        for feature in self.layer.getFeatures():
            if feature[self.field_name] is not None and feature[self.field_name] > 0:
                numbered_features.append({
                    'feature': feature,
                    'old_number': feature[self.field_name]
                })
        
        # Sort by existing number
        numbered_features.sort(key=lambda x: x['old_number'])
        
        # Renumber from 1
        self.layer.startEditing()
        for i, item in enumerate(numbered_features, 1):
            self.layer.changeAttributeValue(
                item['feature'].id(),
                field_idx,
                i
            )
        self.layer.commitChanges()

    def show_warning(self, message):
        QMessageBox.warning(None, "Warning", message)

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu('Auto Numbering', action)
            self.iface.removeToolBarIcon(action)
        
        if self.toolbar:
            del self.toolbar
            
        if self.dock_widget:
            self.dock_widget.close()
            self.iface.removeDockWidget(self.dock_widget)