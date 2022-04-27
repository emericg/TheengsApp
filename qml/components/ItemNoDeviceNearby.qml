import QtQuick 2.15
import QtQuick.Controls 2.15

import ThemeEngine 1.0

Rectangle {
    anchors.centerIn: parent
    anchors.verticalCenterOffset: -24

    width: singleColumn ? (parent.width*0.4) : (parent.height*0.4)
    height: width
    radius: width
    color: Theme.colorForeground

    IconSvg {
        anchors.centerIn: parent
        width: parent.height*0.8
        height: width

        source: "qrc:/assets/icons_material/baseline-radar-24px.svg"
        fillMode: Image.PreserveAspectFit
        color: Theme.colorSubText
        opacity: 0.9
    }

    Text {
        anchors.top: parent.bottom
        anchors.topMargin: 24
        anchors.horizontalCenter: parent.horizontalCenter

        text: qsTr("Looking for nearby devices...")
        textFormat: Text.PlainText
        font.pixelSize: Theme.fontSizeContent
        color: Theme.colorText
    }
}
