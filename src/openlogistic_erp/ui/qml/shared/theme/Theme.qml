pragma ComponentBehavior: Bound

import QtQuick

QtObject {
    readonly property color background: "#f8f9fd"
    readonly property color surface: "#f8f9fd"
    readonly property color surfaceLow: "#f2f4f7"
    readonly property color surfaceMid: "#eceef1"
    readonly property color surfaceHigh: "#e6e8ec"
    readonly property color surfaceRaised: "#ffffff"

    readonly property color primary: "#00478d"
    readonly property color primaryContainer: "#005eb8"
    readonly property color primaryFixed: "#d6e3ff"
    readonly property color secondary: "#496172"
    readonly property color secondaryContainer: "#cce6fa"
    readonly property color outline: "#727783"
    readonly property color outlineVariant: "#c2c6d4"

    readonly property color textPrimary: "#191c1f"
    readonly property color textSecondary: "#496172"
    readonly property color textOnPrimary: "#f7f9ff"
    readonly property color textOnPrimaryMuted: "#d6e3ff"

    readonly property color success: "#1f8b4d"
    readonly property color successContainer: "#dff5e8"
    readonly property color warning: "#a56b08"
    readonly property color warningContainer: "#fce9c8"
    readonly property color danger: "#b13b39"
    readonly property color dangerContainer: "#fde1df"
    readonly property color neutralContainer: "#edf1f5"
    readonly property color disabledContainer: "#eef1f5"
    readonly property color disabledOutline: "#d7dbe3"
    readonly property color disabledText: "#6e7480"
    readonly property color disabledPlaceholderText: "#9097a3"

    readonly property string headlineFontFamily: "Manrope"
    readonly property string bodyFontFamily: "Inter"

    readonly property int controlHeightCompact: 30
    readonly property int controlHeightDefault: 36
    readonly property int controlHeightLarge: 40

    readonly property int spacing2: 8
    readonly property int spacing3: 12
    readonly property int spacing4: 16
    readonly property int spacing5: 20
    readonly property int spacing6: 24
    readonly property int spacing8: 32
    readonly property int spacing10: 40
    readonly property int spacing12: 48

    readonly property int radiusSmall: 12
    readonly property int radiusMedium: 16
    readonly property int radiusLarge: 24
    readonly property int radiusXLarge: 32
    readonly property int radiusPill: 999

    readonly property int displaySize: 26
    readonly property int titleSize: 18
    readonly property int sectionTitleSize: 14
    readonly property int bodySize: 12
    readonly property int captionSize: 10

    function alpha(hexColor, opacity) {
        return Qt.rgba(hexColor.r, hexColor.g, hexColor.b, opacity)
    }
}
