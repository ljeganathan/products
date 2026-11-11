plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.kotmatetn.tableorder"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.kotmatetn.tableorder"
        minSdk = 26
        targetSdk = 34
        versionCode = 1
        versionName = "1.0.0"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("com.google.android.material:material:1.12.0")

    // Ready-made QR scan Activity (camera permission + preview + decode) — staff scans
    // the table's own existing printed QR exactly once, at setup, so there's no reason
    // to hand-roll a CameraX/ML Kit scanner for a screen this app shows maybe twice ever.
    implementation("com.journeyapps:zxing-android-embedded:4.3.0")
}
