// SPDX-FileCopyrightText: 2020 Lukas Schrangl <lukas.schrangl@tuwien.ac.at>
//
// SPDX-License-Identifier: BSD-3-Clause

import QtQuick 2.0
import QtQuick.Controls 2.7


Item {
    id: root

    property real from: 0
    property real to: 100
    property real value: 0
    property int decimals: 2
    property real stepSize: 1.0
    property bool editable: false
    signal valueModified(real value)

    implicitWidth: spin.implicitWidth
    implicitHeight: spin.implicitHeight

    SpinBox {
        id: spin

        property real factor: Math.pow(10, decimals)

        from: clampInt(root.from * factor)
        to: clampInt(root.to * factor)
        value: root.value * factor
        stepSize: root.stepSize * factor
        editable: root.editable

        anchors.fill: parent

        validator: DoubleValidator {
            bottom: Math.min(root.from, root.to)
            top: Math.max(root.from, root.to)
        }

        textFromValue: function(value, locale) {
            return Number(value / factor).toLocaleString(locale, 'f', root.decimals)
        }

        valueFromText: function(text, locale) {
            return Number.fromLocaleString(locale, text) * factor
            //TODO: Maybe try english locale if the above fails?
        }

        onValueModified: {
            var realValue = value / factor
            root.value = realValue
            root.valueModified(realValue)
        }

        function clamp(x, min, max) {
            return Math.min(Math.max(x, min), max)
        }

        // used only below to get integer range
        property var intValidator: IntValidator {}

        function clampInt(x) {
            return clamp(x, intValidator.bottom, intValidator.top)
        }
    }
}
