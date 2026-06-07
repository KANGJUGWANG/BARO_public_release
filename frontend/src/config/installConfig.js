export const INSTALL_CONFIG = {
  webAppUrl: 'https://baro-capstone.vercel.app',
  installPageUrl: 'https://baro-capstone.vercel.app/install',
  githubApkUrl: 'https://github.com/KANGJUGWANG/BARO-Downloads/releases/latest/download/BARO-Android.apk',
  internalAppSharingUrl: import.meta.env.VITE_INTERNAL_APP_SHARING_URL || '',
  androidVersion: '1.7',
  versionCode: 4,
  packageName: 'com.baro.pricebarometer',
  apkSha256: import.meta.env.VITE_APK_SHA256 || '',
}
