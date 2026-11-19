# Çalışma durumu 18 Kasım 2026

## En son: simülasyonla ilk ortak etki adayı (gluteus medius + gluteus maximus)

Aynı hazır kontrolcüyle, aynı başlangıçtan ileri simülasyon taraması yapıldı. Sağ bacakta 8 kas grubu (tibialis anterior, soleus, gastroknemius, vastus, hamstring, gluteus medius, gluteus maximus, kalça fleksörleri) tek tek ve ikişer ikişer %60/%40/%20/%0 aktif kuvvete düşürüldü; 145 simülasyon. Kontrolcünün erken durdurması kapatıldı, her koşu 3 döngü veya düşüşe kadar sürdü. Sonuç sınıfları: yürüdü (ortalama eklem sapması ≤0,06 rad), saptı, düştü (pelvis yüksekliği başlangıcın %70'inin altına indi).

- %60'ta 36 senaryonun hepsi yürüdü. %40 ve %20'de tek gruplar hep yürüdü; %20'de 2 ikili düştü, 1'i saptı.
- Tek tek yürüyüp birlikte başarısız olan 4 aday çıktı. Bunlar 5 tekrar (başlangıçta küçük gürültü, 0,001) ve ince kuvvet adımlarıyla (%50–%10) yeniden test edildi.
- **Sağlam çıkan aday: gluteus medius + gluteus maximus.** Tek tek %20'de 5/5 yürüyor; birlikte %30'da 3/5, %20'de 5/5 düşüyor. Düşüş çoğu tekrarda ilk 0,2–0,3 saniyede başlıyor.
- Kısmen sağlam: gastroknemius + kalça fleksörleri. Birlikte %20 ve %10'da 5/5 sapıyor, düşmüyor. Kalça fleksörleri tek başına da bazı tekrarlarda sınırda.
- Gürültü çıkanlar: vastus + kalça fleksörü (%40) ve vastus + gluteus maximus (%20). Tekrarlarda büyük ölçüde yürüdüler.

Sınırlar: Kontrolcü zayıflığa göre yeniden eğitilmedi, yani bu sonuç "bu kontrolcü uyum sağlayamıyor" demektir; bir insanın ya da uyarlanmış bir kontrolcünün yürüyemeyeceğini göstermez. İki gluteus kası işlevce örtüştüğü için sonuç kas yedekliliğinin kaybıyla açıklanabilir; zamanlama (aktivasyon hızı) hipotezini henüz ayrıca test etmez.

Dosyalar: `results/forward_sweep/` (ızgara, `sweep.png`), `results/forward_sweep_robust/` (tekrarlar), `results/visual_gluteus/` (dört panelli animasyon). Betikler: `scripts/simulate_weakness_sweep.py`, `scripts/analyze_forward_sweep.py`, `scripts/show_weakness_grid.py`. Animasyon: `Kalca_Kaslarini_Goster.cmd`.

## Önceki: tork açığının yeri bulundu (önceki yorumu düzeltir)

Sıradaki deneylerin ilki yapıldı. Ayrıntılar `ILK_SONUCLAR.md` içindeki "Tork açığı nerede?" bölümünde.

- Alt sınırın dual sertifikası, ağırlığın tamamını 2,180–2,182 s arasındaki tek bir 2 ms geçişe koyuyor. Bu an sağ topuğun yere değmesinden hemen sonra ve kontrolcünün bir güncelleme anı. Kontrolcü burada tibialis anterior uyarısını 0,002'den 0,891'e tek adımda çıkarıyor; kayıtlı ayak bileği torku 2 ms'de yaklaşık 28,4 Nm sıçrıyor (döngüdeki ortanca adım değişimi yaklaşık 0,02 Nm).
- Bu tek geçiş çıkarıldığında %80, %60 ve %50 kapasitede alt sınır sıfıra iniyor. %40'ta yalnızca 0,609 Nm kalıyor ve o da aynı olayın hemen ardındaki 2,184–2,188 s örneklerinde.
- Dolayısıyla önceki 1,97–4,21 Nm değerleri sürekli bir yürüyüş özelliği değil, kaydı üreten kontrolcünün tek bir ani komutuna bağlı. Bulgu hâlâ doğru bir sayısal alt sınırdır ama mekanizma iddiası için zayıftır.
- Kayıtlar: `results/torque_gap_location/location.json`, `event_check.json`, `location.png/.pdf`. Betikler: `scripts/locate_torque_gap.py`, `scripts/check_gap_event.py`.

`Kas_Zayifligini_Goster.cmd` ile açılan yan yana karşılaştırma (normal / %40 tibialis anterior) de belgelendi: aynı kontrolcü ve aynı başlangıçla iki ileri simülasyon. %40 durumunda da üç döngü tamamlandı; sağ ayak bileği açısında en fazla 18,7°, sağ ayak parmağı yüksekliğinde en fazla 6,1 cm fark var. Videolar `results/visual_comparison/physical_comparison.mp4` ve `fixed_motion_analysis.mp4`. Görüntüleyicide sağ panelde üst üste binen yazılar düzeltildi ve videolar yeniden üretildi.

## Önceki doğrulanan durum

Devam deneyleri tamamlandı. Ayrıntılar `ILK_SONUCLAR.md` içinde. 10 ms çözünürlükte 48 koşul tarandı; 2 ms çözünürlükte tibialis anterior kaybının zaman sınırlarıyla ayrışması doğrulandı. %40 kalan kapasitede sağ ayak bileği/ayak gevşetilmiş probleminde gerekli en büyük tork hatasının sayısal alt sınırı yaklaşık 4,214 Nm bulundu. Normal koşulda alt sınır sıfır. Bu ilk bulgu tek kas kaybında da var; asıl ikili ortak etki henüz gösterilmedi. 46 koşullu ayrı yeterli çözüm aramasında 19 koşulun uyarı/aktivasyon dizisi yerel MuJoCo fonksiyonuyla doğrulandı. Üç matematiksel otomatik kontrol geçti. `Yuruyusu_Izle.cmd` kayıt oynatıcısı eklendi ve yerel MuJoCo penceresi açıldı. Sonuç grafikleri `results/temporal_margin/pilot_results.png` ve `.pdf` içinde.

Normal yürüyüş, yayınlanmış kontrolcüyle yerel bilgisayarda üç döngü boyunca tamamlandı. Kayıt 1.760 fizik adımı içeriyor. Son kontrol anında model sağlıklı; yürüyüş videosu `results/baseline/normal_walk.mp4`, sayısal kayıt `results/baseline/trajectory.npz`, doğrulama özeti `results/baseline/summary.json` içinde.

İlk zayıflık taraması tamamlandı. İki kuvvet düzeyinde toplam 32 senaryo değerlendirildi. 27 senaryoda anlık koşullar ve kullanılan iyimser zaman sınırları sağlandı; beşinde anlık koşullar zaten sağlanmadığı için zaman taraması yapılmadı. Aranan, anlık olarak mümkün olup zaman sınırıyla elenen örnek bu taramada bulunmadı. Bu sonuç gerçek kas dinamikleriyle uygulanabilirliğin kanıtı değildir. Ayrıntılar `results/weakness_screen/screen.json` içinde.

Kullanıcının yalnızca iki eski önbelleğin taşınmasına verdiği onay kapsamında, C'deki pip önbelleğinin 865 dosyası D'ye kopyalandı ve doğrulandı; ardından C kopyaları kaldırıldı. Toplam yaklaşık 487 MiB. D kopyası `disk_kurtarma/2026-11-18/pip_cache`, işlem kaydı `results/disk_transfer/pip_cache.json` içinde. uv kopyalama işlemi kullanıcı yönlendirmesiyle durduruldu; C'deki uv dosyalarını silme aşamasına geçilmedi. D'de kısmi uv kopyası bulunuyor. Ek temizlik yapılmadı.

Aşağıdaki önceki çalışma notlarında yer alan yürüyüşün tamamlanmadığı ve C'den hiç dosya kaldırılmadığı ifadeleri önceki aşamayı anlatır; güncel durum yukarıdadır.

## Python 3.12 ortamı ve disk denetimi

Python 3.12.13 D diskine `.runtime/python` altına kuruldu. `.venv312` ortamında MuJoCo 3.17.0 içe aktarma ve iki gerçek modelin derlenmesi başarılı. Önceki Python 3.10 ortamındaki DLL engeli bu yeni ortamda yeniden üretilmedi. Güvenlik ayarı değiştirilmedi.

Hazır LocomotionLegs checkpoint'i yayıncı SHA256 değeriyle doğrulanıp `vendor/checkpoints` içine indirildi. Kaydedildiği Stable-Baselines3 2.7.1, Gymnasium 1.2.3 ve NumPy 2.4.2 sürümleri eşlendi. PyTorch 2.10.0 CPU sürümü kuruldu. msgym kaynakları editable olarak `.venv312` ortamına kuruldu. Boş model alt modülü dizinine aynı sabit sürümdeki model dosyaları D içinde kopyalandı.

Kontrolcünün ilk yükleme denemesi, kullanıcının C diski doluluğu uyarısı üzerine durduruldu. Normal yürüyüş tamamlanmış değildir. `scripts/record_baseline.py` kayıt kodu hazırlanıyor; henüz uçtan uca doğrulanmadı.

Salt okunur disk denetiminde C'de yaklaşık 1.67–1.75 GiB, D'de 524 GiB boş alan bulundu. Pagefile D:\pagefile.sys üzerinde. Bu projedeki Python, paket, model ve cache yollarının D'de olduğu doğrulandı. C'deki eski pip ve uv önbelleklerinde son iki saatte değişiklik görülmedi; mevcut toplam büyüklükleri yaklaşık 933 MiB. C'deki `.cache` yaklaşık 2.8 GiB ve onda da aynı zaman diliminde değişiklik görülmedi.

C'deki bazı uygulama günlük dosyaları güncelleniyor. Son iki saatte değişmiş dosyaların mevcut toplam boyutu yaklaşık 125 MiB; bu sayı net büyüme miktarı değildir. Diğer uygulamaların geçici dosyaları da güncelleniyor. Önceki mutlak C'ye yazılmayacağı ifadesi bu gözlemle düzeltilmiştir. Proje süreçlerinin D yollarını kullanması, ana uygulama ve işletim sisteminin tüm yazımlarını denetlemeye yetmez. C'de hiçbir dosya silinmedi veya taşınmadı. Eski iki paket önbelleğinin taşınması için kullanıcıya açık onay soruldu.

## Windows uygulaması kuruldu ve açıldı

MuJoCo 3.17.0 resmî taşınabilir Windows paketi `programs/mujoco-3.17.0` içine kuruldu. Mevcut araştırma ortamındaki 3.17 sürümüyle uyum için bu sürüm seçildi. Arşiv SHA256 değeri yayıncının değeriyle eşleşti. Kurulum kaydı `programs/mujoco-3.17.0/installation.json` içinde.

`compile.exe`, `MS-Human-700-Locomotion.xml` modelini başarıyla derledi ve 0 çıkış kodu döndürdü. Çıktı `results/native_viewer/locomotion.mjb`. Ardından `simulate.exe` masaüstünde modelle açıldı. Pencere başlığı `MuJoCo : MS_Human_700_Locomotion_Model` olarak doğrulandı.

Yeniden açmak için proje kökündeki `Kas_Modelini_Ac.cmd` dosyasına çift tıklanır. Uygulama çalışma dizini ve geçici dosya yolları D diskindeki projeyi kullanır. Model görüntüleme ve yerel motor derlemesi çalışıyor. Aşağıda kayıtlı Python `_structs.pyd` engeli Python tabanlı otomatik deneyler için ayrıca geçerlidir. Hazır yürüyüş kontrolcüsü bu pencereye henüz bağlanmadı.

## Yapılan işler

- Araştırma amacı, hipotez, tork/temas veri gereksinimleri, kontrol koşulları, iki haftalık pilot ve devam ölçütleri `ARASTIRMA_PLANI.md` içine yazıldı.
- Literatür bulguları, erişim sınırları, özgünlük iddiası ve devam edecek sorgular `LITERATUR.md` içine kaydedildi.
- D diski içinde sanal ortam ve bütün çalıştırma komutlarında kullanılan geçici dosya/önbellek ayarları oluşturuldu. `tempfile.gettempdir()`, uv ve pip önbellek yolları D:\projefikri\kas_animasyon altında doğrulandı. Python 3.10 yürütücüsü mevcut C kurulumundan okunuyor. Ek Python kurulumu yapılmadı.
- MuJoCo 3.17.0, NumPy 2.2.6, SciPy 1.15.3 ve bağımlılıkları `.venv` içine kuruldu. Tam liste `requirements-lock.txt` içinde.
- msgym commit `ad3aac166dab3577d7d16b4a03faccef94c7aac7` ve onun model alt modülü MS-Human-700 commit `2d686957aefd5739cf4d2859a6acfd94c8f84400` indirildi. Kaynak SHA256 kayıtları `vendor/sources.json` içinde.
- Üç aktüatörlü sentetik örnek çalıştı. Gerçek kaynak XML'leri ve sayısal NPZ alanları kontrol edildi.

## İlk hesaplama sonucu

`results/synthetic/pilot.json` içindeki iki zaman noktalı, keyfi kuvvet birimli örnekte aşağıdaki durumlar elde edildi.

| Kayıp | Anlar ayrı ele alındığında | Zaman sınırı eklendiğinde |
| --- | --- | --- |
| Kayıpsız | Mümkün | Mümkün |
| A | Mümkün | Mümkün |
| B | Mümkün | Mümkün |
| C | Mümkün | Mümkün |
| A+B | Mümkün | Mümkün değil |
| A+C | Mümkün değil | Mümkün değil |
| B+C | Mümkün değil | Mümkün değil |

A+B kaybında kalan C aktüatörünün kuvveti 0.45'ten 0.80'e çıkmalıdır. İzin verilen değişim 0.10 olduğu için 0.35'lik değişim yapılamaz. Bu bağımsız aritmetik kontrol LP sonucunu doğrular. Örnek tam aktüatör kaybını ve basit değişim sınırını kullanır. Gerçek kas fizyolojisi, yürüyüş veya özgünlük kanıtı oluşturmaz.

## Gerçek kaynak denetimi

- `walking_gait.npz` dosyasında 117 kare, 100 Hz, 85 konum koordinatı ve 81 gövde için üç boyutlu konum kaydı bulundu.
- Kaynaktaki çevrim süresi 1.17 saniye. İlk ve son örneğin zaman farkı 1.16 saniye. Çevrim sınırını ve pelvisin ileri hareketini türev hesabında ayrıca düzeltmek gerekir.
- XML denetiminde tam modelde 85 eklem ve 700 aktüatör, alt gövde modelinde 36 eklem ve 100 aktüatör bulundu.
- Alt gövde eklem adları tam modelde mevcut. XML boyut uyumu sağlandı. Gerçek derlenmiş modelle referans koordinat sırası henüz doğrulanmadı.
- Sayısal alanlarda sonlu değerler kontrol edildi. `array_descriptions` nesne metaverisi pickle gerektirdiği için yüklenmedi. Diğer sayısal alanlar okunabildi.
- Hazır kayıtta dış yük veya yer tepki kuvveti alanı bulunmadı. Gerçek zayıflık deneyi öncesinde bu veri uygun bir kontrolcü çalıştırmasından veya bağımsız dış yüklü bir kayıttan elde edilmeli.
- `results/model_audit/audit.json` ayrıntılı kaydı, `reference_coordinates.csv` zaman ve kaynak indisleriyle koordinatları içerir. Bu CSV'deki sütunlara henüz anatomik isim atanmamıştır.

## Aktif teknik engel

MuJoCo içe aktarılırken Windows aşağıdaki hatayı verdi.

```
ImportError: DLL load failed while importing _structs:
Uygulama Denetimi ilkesi bu dosyayı engelledi.
```

Bu nedenle XML'lerin MuJoCo'da derlenmesi, fiziksel simülasyon ve gerçek kas zayıflığı deneyi henüz çalıştırılamadı. Motor çalıştırıldıktan sonra kod/veri eşlemesi doğrulanacak.

18 Kasım 2026 tarihindeki ek tanıda, yükseltilmiş salt okunur erişimle Code Integrity olayları okunabildi. 3077 ve 3033 olayları `.venv/Lib/site-packages/mujoco/_structs.cp310-win_amd64.pyd` dosyasının engellendiğini doğruladı. Olaydaki ilke kimliği `{0283ac0f-fff1-49ae-ada1-8a933130cad6}`, Microsoft'un VerifiedAndReputableDesktop yani Akıllı Uygulama Denetimi ilkesine karşılık geliyor. `VerifiedAndReputablePolicyState=1` değeri de açık durumuyla uyumlu. Windows ayarlarında ilgili bölüm Windows Güvenliği > Uygulama ve tarayıcı denetimi > Akıllı Uygulama Denetimi.

Microsoft'un açıklamasına göre Akıllı Uygulama Denetimi uygulama başına istisna sağlamıyor. Dolayısıyla bu dosyaya tekil izin verileceği şeklindeki önceki varsayım düzeltilmiştir. Herhangi bir güvenlik ayarı değiştirilmedi. İlerlemek için uygun imzalı bir dağıtımın kullanılabilirliği veya kullanıcının onaylayacağı başka bir çalıştırma ortamı değerlendirilmelidir. [İlke kimlikleri](https://learn.microsoft.com/en-us/windows/security/application-security/application-control/windows-defender-application-control/operations/inbox-wdac-policies), [Microsoft sık sorulan sorular](https://support.microsoft.com/en-gb/windows/security/threat-malware-protection/smart-app-control-frequently-asked-questions).

msgym paketinin `pyproject.toml` dosyası Python >=3.12 istiyor. Şu anki Python 3.10 ortamı sayısal örnek ve XML/NPZ denetimi için kullanıldı. msgym kontrolcüsü aşamasında D diskine ayrı Python 3.12 kurulumu ve uyumlu bağımlılıklar hazırlanmalı. Hazır checkpoint henüz indirilmedi veya yüklenmedi.

## Sonraki somut işler

1. Akıllı Uygulama Denetimiyle uyumlu bir dağıtım veya onaylanmış çalıştırma ortamı sağlandıktan sonra `scripts/audit_model.py` komutunda `compiled=true` elde et.
2. D diski içinde Python 3.12 ortamında uygun checkpoint/kod/normalizasyon eşleşmesini kur veya dış yükleri bulunan referans veriyi kullan.
3. Bir normal adımın eklem torku ve temas dengesini doğrula. Modelin başlangıçta bu adımı karşılayabildiğini göster.
4. Anatomik kas gruplarını kaydet, tekli kapasite düşüşlerini tara, ardından ikili ve zamana bağlı karşılaştırmaları başlat.

## Yeniden çalıştırma

```powershell
. .\scripts\environment.ps1
.venv\Scripts\python.exe scripts\synthetic_pilot.py
.venv\Scripts\python.exe scripts\audit_model.py
```

Kaynak kodu, ortam, önbellek ve verinin başlangıçtaki toplam mantıksal dosya büyüklüğü yaklaşık 512 MiB olarak ölçüldü. Önbellekte ve sanal ortamda aynı paketlerin kopyaları bulunduğu için disk kullanımının bir kısmı tekrarlıdır.
