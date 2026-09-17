package com.imankoppai.mediaanvil.update

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class AppUpdateCheckerTest {
    @Test fun comparesReleaseVersions() {
        assertTrue(AppUpdateChecker.isNewer("v1.5", "1.4"))
        assertTrue(AppUpdateChecker.isNewer("1.4.1", "1.4"))
        assertFalse(AppUpdateChecker.isNewer("v1.4", "1.4"))
        assertFalse(AppUpdateChecker.isNewer("v1.3.9", "1.4"))
    }
}
