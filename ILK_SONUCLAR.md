# İlk gerçek model sonuçları

## Basit açıklama

Normal yürüyüşü bilgisayarda çalıştırdık ve kaydettik. Ardından bazı kasların kuvvetini azaltıp aynı yürüyüşün gerektirdiği torkların karşılanıp karşılanamayacağını hesapladık.

İlk aday mekanizma bulundu. Sağ kavalın ön tarafındaki tibialis anterior kasını zayıflattığımızda, anları ayrı ayrı değerlendiren hesap yeterli kuvvet buluyor. Kasların bir andan diğerine ne kadar hızlı etkinleşip gevşeyebileceğini eklediğimizde hedefin tam karşılanması mümkün görünmüyor. Bu sonuç, kaydedilmiş belirli yürüyüş ve model için sayısal bir bulgudur.

## Ne yaptık?

- Yayınlanmış LocomotionLegs kontrolcüsüyle üç yürüyüş döngüsü tamamlandı. Toplam 1.760 fizik adımı kaydedildi. Video `results/baseline/normal_walk.mp4` içinde.
- Normal yürüyüşün ikinci döngüsündeki 1,17–2,34 saniye aralığı incelendi. Sık kontrol 2 ms aralıkla 586 durumu içeriyor. İlk ve son durum aynı olmak zorunda tutulmadı; başlangıç aktivasyonu serbest.
- Beş anatomik kas grubunun tekli ve ikili kayıpları, %80, %60 ve %40 kalan aktif kuvvet düzeylerinde tarandı. Pasif kuvvetler sabit kaldı.
- Daha kaba 10 ms taramada 48 koşulun 34'ü iki koşulu da sağladı; 10'u anlık tork koşulunda elendi; dördü yalnızca zaman sınırları eklenince elendi. Bu son dört koşulun tamamında tibialis anterior kaybı var. Üçü başka bir grupla birleşim olsa da tekli kayıp zaten elendiği için hedeflenen ortak etkiye kanıt sayılmaz.
- Ayrı bir yeterli-çözüm araması 46 koşulun 19'unda bütün torkları ve yerel MuJoCo aktivasyon adımlarını doğrulayan uyarı dizileri üretti. Kalan 27 koşul bu yöntemle doğrulanamadı. Bu 27 koşulun tamamı için olanaksızlık sonucu çıkarılamaz.

## Daha sık kontrolden ne çıktı?

Tibialis anterior için tam modelin bütün tork denklemleri kullanıldığında, %80, %60, %50 ve %40 kapasitede anlık hesap mümkün kaldı; iyimser zaman sınırları eklenince tam tork eşitliği sağlanamadı. %80'deki fark çok küçük olduğu için büyüklüğü ayrıca önemlidir.

Sağ ayak bileği, subtalar ve ayak parmağı eklemlerinin üç dönme koordinatını ve bunları etkileyen 11 kası içeren daha kolay bir problemde gerekli tork hatasının alt sınırı hesaplandı. Diğer eklemlerin koşullarını kaldırmak problemi kolaylaştırır. Bu kolaylaştırılmış problemde bile pozitif minimum hata bulunması, tam problemdeki gerekli hataya sayısal bir alt sınır verir.

| Tibialis anterior kalan aktif kuvveti | Zamanlar bağımsızken minimum en büyük hata | Zaman sınırlarıyla minimum en büyük hata |
| --- | --- | --- |
| %100 | 0 Nm | 0 Nm |
| %80 | 0 Nm | 0,0374 Nm |
| %60 | 0 Nm | 1,9706 Nm |
| %50 | 0 Nm | 3,0923 Nm |
| %40 | 0 Nm | 4,2140 Nm |

Bu değerler gerçek kas modelindeki hatanın kesin değeri değildir. Gerçek aktivasyon dinamiğinin izin verdiğinden daha fazla geçişe izin veren dış sınırlar kullanıldığı için, doğrulanmış sayısal LP sonuçları koşullu alt sınır olarak yorumlanır. Uygulanan kuvvet kaybı yalnızca aktif bileşene aittir; klinik hastalık modeli değildir.

Aktivasyon zaman sabitleri yarıya indirildiğinde aynı iyimser hesapta bu hataların tamamı sıfıra indi. Bu, zaman sınırlarına duyarlılığı gösterir. Hızlandırılmış gerçek kas modelinde tam çözüm bulunduğunu kanıtlamaz.

## Tork açığı nerede?

Alt sınırın dayandığı denklemler, doğrusal programın dual çarpanlarıyla bulundu (tek bir minimax çözümünün zaman profili tek değildir, bu yüzden dual sertifika kullanıldı).

- Ağırlığın tamamı 2,180→2,182 s geçişinde. Sağ ayak bu sırada yere yeni basmış durumda ve bu an kontrolcünün 20 ms'lik güncellemelerinden birine denk geliyor.
- Kontrolcü bu güncellemede tibialis anterior uyarısını 0,002'den 0,891'e çıkarıyor. Kayıtlı aktivasyon bir fizik adımında 0,004'ten 0,354'e, ayak bileği hedef torku −2,3 Nm'den 26,1 Nm'ye geçiyor. Döngünün geri kalanında tipik adım değişimi yaklaşık 0,02 Nm.
- Bağlayıcı aktivasyon sınırları, tibialis anterior ile diğer ön kasların (EDL, EHL) yükselme hızı ve peroneusların gevşeme hızı.

| Kalan kuvvet | Tam döngü alt sınırı | Bu geçiş çıkarıldığında |
| --- | --- | --- |
| %80 | 0,0374 Nm | 0 Nm |
| %60 | 1,9706 Nm | 0 Nm |
| %50 | 3,0923 Nm | 0 Nm |
| %40 | 4,2140 Nm | 0,609 Nm (2,184–2,188 s, aynı olayın hemen sonrası) |

Yorum: Önceki tablodaki değerler, sürekli bir zamanlama kısıtından değil, kaydı üreten kontrolcünün topuk temasındaki tek bir ani komutundan kaynaklanıyor. Hedef hareket aynen korunmak zorunda olduğu için bu sıçrama zayıf kasla aynı 2 ms içinde üretilemiyor. Hareketin bu anda birkaç milisaniye kayması büyük olasılıkla açığı kapatır. Bu nedenle bulgu, mekanizma kanıtı olarak değil, kontrolcüye ve kayda özgü bir sonuç olarak değerlendirilmelidir. Sonraki adımda hedef hareket bu olay çevresinde küçük zaman kaymalarına izin verecek şekilde gevşetilmeli veya daha yumuşak uyarı üreten bir kayıt kullanılmalı.

Dosyalar: `results/torque_gap_location/location.json`, `event_check.json`, `location.png`. Betikler: `scripts/locate_torque_gap.py`, `scripts/check_gap_event.py`.

## Normal ve zayıf yürüyüşün yan yana görüntüsü

`Kas_Zayifligini_Goster.cmd` aynı başlangıç durumu ve aynı hazır kontrolcüyle iki ileri simülasyonu yan yana oynatır: normal ve sağ tibialis anterior aktif kuvveti %40. TAB tuşu, sabit hedef hareket üzerindeki tork analizi görünümüne geçer. %40 durumunda da üç döngü sağlıklı tamamlandı; sağ ayak bileği açısında en fazla 18,7°, sağ ayak parmağı yüksekliğinde en fazla 6,1 cm fark oluştu. Videolar `results/visual_comparison/` içinde. Bu ileri simülasyon yalnızca bu kontrolcünün tepkisini gösterir.

## Doğrulama ve sınırlar

- Formüller, kurulu MuJoCo 3.17.0'ın `mju_muscleDynamics` fonksiyonuyla kontrol edildi. Kaydedilmiş normal aktivasyon adımları aynı fonksiyonla yeniden üretildi.
- Alt sınır hesabının primal kısıt ihlali en fazla yaklaşık 9,85e-9; dual denge hatası en fazla yaklaşık 5,86e-13. Primal ve dual amaç değerleri yaklaşık kayan nokta duyarlığında eşleşti. Bu bir aralık aritmetiğiyle kesin ispat değildir.
- Üç otomatik kontrol geçti: yerel motorla aktivasyon formüllerinin eşleşmesi, yeterli çözüm için kullanılan teğet sınırlarının yönü, analitik çözümü 0,375 olan iki zamanlı örneğin yeniden bulunması.
- Tek model, tek kontrolcü ve tek yürüyüş kaydı kullanıldı. Sonuç, kişinin yürüyemeyeceğini göstermez. Başka bir hareket veya daha yavaş yürüyüş telafi sağlayabilir.
- %80 koşulundaki yaklaşık 0,037 Nm fark çok küçüktür; klinik önem iddiası yapılmaz. Daha büyük farkların da kayıt, temas, kontrolcü ve model duyarlılığı araştırılmalıdır.
- İki kas grubu tek tek zaman bakımından yeterliyken birlikte yetersiz olması şeklindeki asıl hipotez henüz gösterilmedi. Özgünlük ve yayın değeri kesinleşmedi.

## Sıradaki deneyler

1. ~~Tork açığının zamanını, eklemini ve kas geçişini bul.~~ Yapıldı: açık tek bir kontrolcü güncellemesine bağlı (yukarıda). Yeni madde: hedef hareketi bu olay çevresinde birkaç ms zaman kaymasına izin verecek şekilde gevşet ve alt sınırın kalıp kalmadığına bak.
2. Farklı başlangıçlar ve yürüyüş döngülerinde aynı deneyi tekrarla. Tek döngüye veya kontrolcüye özgü keskin geçişleri ayır.
3. Telafiye katılan ayak bileği kaslarından yeni anatomik grup listesi belirle. Tekli kayıpların zaman bakımından mümkün kaldığı kapasite aralıklarında ikili kayıpları ara.
4. Gerçek aktivasyon denklemiyle yeterli çözümleri ve iyimser sınırlarla olanaksızlık adaylarını birlikte değerlendir; çözücü başarısızlığını mekanizma sonucu sayma.
5. Bağımsız kayıt/model ve ilgili literatür karşılaştırmasıyla sonuçların genellenebilirliğini ve özgün katkıyı değerlendir.

## Dosyalar ve tekrar çalıştırma

- `results/weakness_screen_refined/screen.json`: 48 koşul, 10 ms tarama.
- `results/activation_validation/validation.json`: 46 koşul, 2 ms yeterli çözüm doğrulaması. Başarılı koşulların aktivasyon ve uyarıları aynı klasördeki NPZ dosyalarında.
- `results/temporal_candidate/screen.json`: tibialis anterior için 2 ms tam tork denklemleri.
- `results/temporal_margin/margin.json`: alt sınır, zaman sabiti duyarlılığı ve sayısal doğrulamalar.
- `results/temporal_margin/pilot_results.png` ve `.pdf`: dışa aktarılabilir sonuç grafikleri.
- `Yuruyusu_Izle.cmd`: kaydedilmiş normal yürüyüşün yerel MuJoCo oynatıcısı. Yeni kontrol deneyi çalıştırmaz; kayıt oynatır.

Proje klasöründeki PowerShell'de:

```powershell
. .\scripts\environment.ps1
$env:OMP_NUM_THREADS='1'
.\.venv312\Scripts\python.exe scripts\test_temporal_analysis.py
.\.venv312\Scripts\python.exe scripts\screen_feasibility.py --stride 5 --start 1.17 --duration 1.17 --remaining 0.8 0.6 0.4 --output results/weakness_screen_refined
.\.venv312\Scripts\python.exe scripts\validate_activation_dynamics.py --remaining 0.8 0.6 0.4 --pairs
.\.venv312\Scripts\python.exe scripts\screen_feasibility.py --stride 1 --start 1.17 --duration 1.17 --remaining 0.8 0.6 0.5 0.4 --scenario right_tibialis_anterior --output results/temporal_candidate
.\.venv312\Scripts\python.exe scripts\check_temporal_margin.py
.\.venv312\Scripts\python.exe scripts\plot_pilot_results.py
```

Aktivasyon denkleminin sürüme sabitlenmiş birincil kaynağı: https://github.com/google-deepmind/mujoco/blob/3.17.0/src/engine/engine_util_misc.c
