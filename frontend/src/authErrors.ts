import { ApiError } from './api'

// Backend hata mesajları zaten Türkçe (409/400 gibi); bağlantı ve limit hataları burada çevrilir.
export function authErrorText(err: unknown): string {
  if (!(err instanceof ApiError)) return 'Bir hata oluştu, tekrar dene.'
  if (err.status === 0) return 'Bağlantı hatası, internetini kontrol et.'
  if (err.status === 429) return 'Çok fazla deneme yapıldı, biraz sonra tekrar dene.'
  if (err.status === 422) return 'Bilgilerini kontrol et: geçerli bir e-posta gir, şifre en az 8 karakter olsun.'
  return err.message
}
