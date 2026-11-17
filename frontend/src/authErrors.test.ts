import { describe, expect, it } from 'vitest'
import { ApiError } from './api'
import { authErrorText } from './authErrors'

describe('authErrorText', () => {
  it('ApiError olmayan hata için genel mesaj', () => {
    expect(authErrorText(new Error('x'))).toBe('Bir hata oluştu, tekrar dene.')
    expect(authErrorText('metin')).toBe('Bir hata oluştu, tekrar dene.')
    expect(authErrorText(undefined)).toBe('Bir hata oluştu, tekrar dene.')
  })

  it('bağlantı hatası (status 0)', () => {
    expect(authErrorText(new ApiError(0, 'Sunucuya ulaşılamadı'))).toBe('Bağlantı hatası, internetini kontrol et.')
  })

  it('hız limiti (429) ve geçersiz girdi (422) çevrilir', () => {
    expect(authErrorText(new ApiError(429, 'x'))).toContain('Çok fazla deneme')
    expect(authErrorText(new ApiError(422, 'x'))).toContain('en az 8 karakter')
  })

  it("diğer durumlarda backend'in Türkçe mesajı aynen gösterilir", () => {
    expect(authErrorText(new ApiError(409, 'Bu e-posta ile zaten bir hesap var'))).toBe(
      'Bu e-posta ile zaten bir hesap var',
    )
    expect(authErrorText(new ApiError(401, 'E-posta veya şifre hatalı'))).toBe('E-posta veya şifre hatalı')
  })
})
