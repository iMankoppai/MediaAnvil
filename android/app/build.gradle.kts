import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.plugin.compose")
}

val localSigningFile = rootProject.file("signing.properties")
val localSigning = Properties().apply {
    if (localSigningFile.isFile) localSigningFile.inputStream().use(::load)
}
fun signingValue(property: String, environment: String): String? =
    localSigning.getProperty(property)?.takeIf(String::isNotBlank)
        ?: System.getenv(environment)?.takeIf(String::isNotBlank)

val releaseStoreFile = signingValue("storeFile", "MEDIAANVIL_KEYSTORE_PATH")
val releaseStorePassword = signingValue("storePassword", "MEDIAANVIL_KEYSTORE_PASSWORD")
val releaseKeyAlias = signingValue("keyAlias", "MEDIAANVIL_KEY_ALIAS")
val releaseKeyPassword = signingValue("keyPassword", "MEDIAANVIL_KEY_PASSWORD")
val hasReleaseSigning = listOf(
    releaseStoreFile,
    releaseStorePassword,
    releaseKeyAlias,
    releaseKeyPassword,
).all { !it.isNullOrBlank() }

android {
    namespace = "com.imankoppai.mediaanvil"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.imankoppai.mediaanvil"
        minSdk = 26
        targetSdk = 36
        versionCode = 17
        versionName = "1.9"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    signingConfigs {
        if (hasReleaseSigning) {
            create("release") {
                storeFile = file(checkNotNull(releaseStoreFile))
                storePassword = releaseStorePassword
                keyAlias = releaseKeyAlias
                keyPassword = releaseKeyPassword
            }
        }
    }

    buildTypes {
        release {
            signingConfigs.findByName("release")?.let { signingConfig = it }
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    buildFeatures {
        compose = true
    }

    packaging {
        resources.excludes += "/META-INF/{AL2.0,LGPL2.1}"
    }
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2025.08.00")
    implementation(composeBom)
    androidTestImplementation(composeBom)

    implementation("androidx.activity:activity-compose:1.11.0")
    implementation("androidx.core:core-ktx:1.17.0")
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.documentfile:documentfile:1.1.0")
    implementation("androidx.media3:media3-common:1.11.0")
    implementation("androidx.media3:media3-exoplayer:1.11.0")
    implementation("androidx.media3:media3-session:1.11.0")
    implementation(files("libs/jaudiotagger-2.3.15.jar"))
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.10.2")
    debugImplementation("androidx.compose.ui:ui-tooling")
    testImplementation("junit:junit:4.13.2")
}
