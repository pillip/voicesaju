/**
 * VoiceSaju v1 design system tokens (ISSUE-021).
 *
 * Authoritative source: docs/design_system.md. v2 "Ink, Amber & 印" tokens
 * land in ISSUE-091 (later sprint) — do NOT conflate.
 *
 * Category color hexes are exact per design_system.md §"Color — Category
 * Signatures" and are exercised by both unit (vitest) and e2e (playwright)
 * tests in this PR.
 */
import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./src/app/**/*.{js,ts,jsx,tsx,mdx}', './src/components/**/*.{js,ts,jsx,tsx,mdx}'],
  theme: {
    extend: {
      colors: {
        // v1 category signatures — design_system.md
        category: {
          love: '#9B4A4A',
          work: '#3D5266',
          money: '#A67C28',
          tarot: '#5B3A5C',
        },
        // Ink scale (base surfaces)
        ink: {
          950: '#080603',
          900: '#0F0B08',
          800: '#1A140F',
          700: '#241B14',
          600: '#2E2419',
          500: '#3A2E22',
          400: '#4A3B2C',
        },
        // Cream scale (text)
        cream: {
          50: '#F5EDD7',
          100: '#EAE0CC',
          200: '#D4C8AC',
          300: '#B0A48A',
          400: '#8A7E66',
          500: '#6A604E',
          600: '#4D4538',
        },
        // Amber scale (accents)
        amber: {
          200: '#E8C896',
          300: '#D9A968',
          400: '#C28E4D',
          500: '#A87639',
          600: '#8B5E2A',
        },
        // Semantic states
        state: {
          success: '#6B8F5C',
          warning: '#D9A968',
          error: '#B05544',
          info: '#6B7C8A',
        },
      },
      fontFamily: {
        display: ['EB Garamond', 'Gowun Batang', 'Georgia', 'serif'],
        'display-han': ['Gowun Batang', 'EB Garamond', 'serif'],
        body: [
          'Pretendard',
          'IBM Plex Sans',
          '-apple-system',
          'BlinkMacSystemFont',
          'system-ui',
          'sans-serif',
        ],
        mono: ['JetBrains Mono', 'D2Coding', 'monospace'],
        sans: [
          'Pretendard',
          '-apple-system',
          'BlinkMacSystemFont',
          'system-ui',
          'Roboto',
          'Helvetica Neue',
          'Segoe UI',
          'Apple SD Gothic Neo',
          'Noto Sans KR',
          'sans-serif',
        ],
      },
      // 4px base spacing scale (Tailwind defaults are already 4px-based;
      // we expose explicit anchors so designers can reference s1..s8 by name).
      spacing: {
        s0: '0px',
        s1: '4px',
        s2: '8px',
        s3: '12px',
        s4: '16px',
        s5: '20px',
        s6: '24px',
        s8: '32px',
        s10: '40px',
        s12: '48px',
      },
      borderRadius: {
        none: '0',
        sm: '2px',
        md: '4px',
        pill: '9999px',
      },
    },
  },
  plugins: [],
};

export default config;
