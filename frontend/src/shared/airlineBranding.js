import JejuAirLogo from '../assets/airlines/7C-jejuair-logo.png'
import KoreanAirLogo from '../assets/airlines/KE-koreanair-logo-2025.png'
import JinAirLogo from '../assets/airlines/LJ-jinair-h1_logo.gif'
import AsianaLogo from '../assets/airlines/OZ-asiana-logo-kor.png'
import AirSeoulLogo from '../assets/airlines/RS-airseoul-logo.jpg'
import TwayLogo from '../assets/airlines/TW-tway-logo-eng.svg'
import AirBusanLogo from '../assets/airlines/BX-airbusan-logo.png'
import AirPremiaLogo from '../assets/airlines/YP-airpremia-logo-preview-ko-20240808.png'
import ZipairLogo from '../assets/airlines/ZG-zipair-logo.svg'
import PeachLogo from '../assets/airlines/MM-peach-logo.svg'
import EthiopianLogo from '../assets/airlines/ET-ethiopian-primary-logo.png'

export const AIRLINE_BRANDING = {
  '7C': {
    code: '7C',
    displayName: '제주항공',
    color: '#FF5000',
    colorType: 'official',
    logo: JejuAirLogo,
    logoUsage: 'identification',
  },
  KE: {
    code: 'KE',
    displayName: '대한항공',
    color: '#0066B3',
    colorType: 'substitute',
    logo: KoreanAirLogo,
    logoUsage: 'identification',
  },
  LJ: {
    code: 'LJ',
    displayName: '진에어',
    color: '#547A23',
    colorType: 'substitute',
    logo: JinAirLogo,
    logoUsage: 'identification',
  },
  OZ: {
    code: 'OZ',
    displayName: '아시아나항공',
    color: '#A30D2D',
    colorType: 'substitute',
    logo: AsianaLogo,
    logoUsage: 'identification',
  },
  RS: {
    code: 'RS',
    displayName: '에어서울',
    color: '#007A6B',
    colorType: 'substitute',
    logo: AirSeoulLogo,
    logoUsage: 'identification',
  },
  TW: {
    code: 'TW',
    displayName: '티웨이항공',
    color: '#D22C26',
    colorType: 'official',
    logo: TwayLogo,
    logoUsage: 'identification',
  },
  BX: {
    code: 'BX',
    displayName: '에어부산',
    color: '#1E409A',
    colorType: 'official',
    logo: AirBusanLogo,
    logoUsage: 'identification',
  },
  YP: {
    code: 'YP',
    displayName: '에어프레미아',
    color: '#1F3B73',
    colorType: 'substitute',
    logo: AirPremiaLogo,
    logoUsage: 'identification',
  },
  ZG: {
    code: 'ZG',
    displayName: 'ZIPAIR',
    color: '#5B6168',
    colorType: 'substitute',
    logo: ZipairLogo,
    logoUsage: 'identification',
  },
  MM: {
    code: 'MM',
    displayName: 'Peach Aviation',
    color: '#A01E46',
    colorType: 'substitute',
    logo: PeachLogo,
    logoUsage: 'identification',
  },
  ET: {
    code: 'ET',
    displayName: 'Ethiopian Airlines',
    color: '#7D6416',
    colorType: 'substitute',
    logo: EthiopianLogo,
    logoUsage: 'identification',
  },
}

export function getAirlineBranding(code, fallbackName) {
  const key = String(code || '').trim().toUpperCase()
  return AIRLINE_BRANDING[key] || {
    code: key || 'XX',
    displayName: fallbackName || key || '항공사',
    color: '#475569',
    colorType: 'fallback',
    logo: null,
    logoUsage: 'fallback_badge',
  }
}
