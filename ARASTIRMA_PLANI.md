# Kas grubu zayıflıkları altında sabit yürüyüşün korunması

## Amaç ve kapsam

Belirli bir referans yürüyüşün eklem hareketleri ve dış yükleri sabit tutulduğunda, kalan kasların gerekli torkları zaman boyunca üretebilmesini değerlendireceğiz. Tek tek telafi edilen kas grubu kapasite kayıplarının birlikte olduğunda oluşturduğu sınırları arayacağız. Yavaşlama, farklı adım uzunluğu veya farklı hareket biçimine izin veren bir yürüyüşün mümkün olup olmadığı ayrı bir araştırma sorusudur.

Araştırmanın hedefi, her anda yeterli kapasite bulunduğu hâlde aktivasyon geçişlerinin aynı hareketi sürdürmeye yetmediği bir kombinasyonun varlığını ve nedenini göstermektir. Böyle bir örneğin gerçek modelde ortaya çıkacağı henüz bilinmiyor.

## Sınanacak hipotez

Tanımlı bir kas grubu listesi ve önceden belirlenmiş zayıflık şiddetinde A ve B kayıpları ayrı ayrı zamana bağlı bir çözümle telafi edilebilir. A+B kaybında her andaki tork hedefi ayrı ayrı karşılanabilir, fakat tüm zamanlar aktivasyon dinamiğiyle bağlandığında çözüm bulunamaz veya hedef toleransı aşılır.

İkili bir örnek ancak tekli senaryoların tamamı aynı koşullarda mümkünse seçilen grup listesi içinde en küçük kardinaliteli örnek sayılır. Daha büyük kümeler için gerçek minimum iddiası bütün daha küçük kümelerin değerlendirilmesini veya doğrulanmış bir optimizasyon sınırını gerektirir. Bir grubun fizyolojik olarak çok sayıda kas içermesi raporda açıkça belirtilir.

## Kullanılacak kaynaklar

- LNSGroup/MS-Human-700 model XML ve varlıkları. Başlangıçta tam ve alt gövde modellerini yükleyip boyutlarını doğrulayacağız.
- LNSGroup/msgym içindeki `msgym/motion_data/walking_gait.npz`. İçeriği yüklenerek alan, şekil ve sonlu değer denetimi yapılacak. Katılımcı ve kayıt kökeni doğrulanmadan insan popülasyonuna genelleme yapılmaz.
- Gerektiğinde GitHub `Checkpoints` sürümündeki LocomotionLegs/LocomotionFull. Checkpoint, kendi kod commit'i, model sürümü ve normalizasyon istatistikleriyle birlikte çalıştırılmalıdır. Yalnızca dosyanın varlığı çalışırlık kanıtı değildir.
- İkinci aşamada bağımsız yürüyüş kayıtları veya ikinci kas-iskelet modeli. Gait120 olası veri kaynağıdır. Erişim, lisans, koordinat dönüşümü ve dış yük kullanılabilirliği önce doğrulanacak.

## Veri ve ölçümler

Referans için zaman, q, qdot, qddot, eklem adları, ayak-yer temas kuvvetleri ve torkları, kas aktivasyonları, aktüatör kuvvetleri ve bunların genelleştirilmiş eklem torklarına eşlemesi gerekir. Yalnızca poz kaydı, yürüyüşte gereken torku güvenilir biçimde belirlemeye yeterli değildir. Kaynakta dış yükler yoksa uygun kontrolcünün fiziksel yürüyüşünden bunlar kaydedilir veya dış yükleri içeren bağımsız kayıt kullanılır.

Gövde koordinatlarını ve dizde bağlı koordinatları indis keserek eşlemek yerine ad, eklem tipi, eksen ve kısıt denetimi yapılır. Bağlı diz hareketlerinde moment kolu ve torklar bağımsız koordinatlara uygun şekilde taşınır. Kas kuvveti işaretleri MuJoCo aktüatör aktarımıyla kontrol edilir.

## Deney düzeni

1. Referans adımın sonlu ve tekrarlanabilir olduğunu, ayak temasının ve baz çizgisi tork dengesinin kabul edilen hata içinde bulunduğunu doğrula.
2. Anatomik kas gruplarını ad listeleriyle kaydet. İki eklemi geçen kaslar ve sağ/sol tarafları açıkça tanımla. Kasın hangi gruba dahil olduğu önceden sabitlensin.
3. Kuvvet kapasitesini ölçekle. İlk tarama için kalan kuvvet oranları 1.0, 0.8, 0.6, 0.4 seçildi. Bunlar pilot tercihidir, klinik eşik değildir. Pasif kuvvetlerin ve tendon parametrelerinin hangi ölçüde değiştiğini kaydet. Yalnızca aktif kuvvet kaybıyla birlikte toplam mekanik parametre değişiminin etkisini karıştırma.
4. Her zaman noktasında aynı tork hedefini, aynı kuvvet-uzunluk-hız ilişkisini ve aynı aktivasyon sınırlarını kullanarak bağımsız çözüm ara.
5. Bütün noktaları ortak başlangıç ve çevrim koşulları altında bağla. İlk hızlı taramada aktivasyon değişimine yaklaşık sınır konabilir. Fizyolojik sonuç için MuJoCo aktivasyon dinamiğiyle ve 0–1 uyarı sınırlarıyla doğrulama yap.
6. Önce tekli kayıpları sonra ikili kayıpları değerlendir. Sentetik örnekteki tam kas kapatma, gerçek pilotta kısmi kapasite azalmasıyla genişletilecek.
7. Zaman sınırını kaldırma, zaman sabitlerini değiştirme, farklı başlangıç durumları ve zaman çözünürlüğü deneyleriyle mekanizmayı kontrol et.
8. Gerçekçi hızlarda ve birden fazla bağımsız kayıtta tekrarla. Yapay zaman ölçeklemesi aynı kayıt üzerindeki duyarlılık deneyi sayılır.

İki çözüm arasındaki temel fark zamana bağlı kısıttır. Bağımsız yöntemin maliyet fonksiyonundan kaynaklanan farklı aktivasyonlar tek başına uygulanamazlık kanıtı oluşturmaz.

## Sonuçları nasıl yorumlayacağız

Kapasite yetersizliği, zamansal yetersizlik, sayısal başarısızlık ve veri/koordinat uyumsuzluğu ayrı durum kodlarıyla kaydedilecek. Bu ayrım hangi mekanizmayı sınadığımızı belirler.

Bir doğrusal program yalnızca kendi tanımlı doğrusal modelinde uygulanamazlık kanıtı sağlayabilir. Yaklaşık LP sonucu fizyolojik modelin tamamı için otomatik kanıt değildir. Nonlineer çözücünün yakınsamaması da imkânsızlık sonucuna yeterli değildir. Birden fazla başlangıç, ağ inceltme, tolerans denetimi ve mümkün olduğunda gevşetilmiş problemde alt sınır kullanılacak. Sabit kontrolcünün düşmesi bu ayrımı çözmez.

## Birincil ve yardımcı çıktılar

Birincil çıktı, bağımsız çözümün mümkün kaldığı fakat zamana bağlı çözümün kaybolduğu kapasite oranı aralığı ve ilgili kas grubu kombinasyonudur. Yardımcı çıktılar, adımın hangi bölümünde tork açığının başladığı, hangi eklemde olduğu, yaklaşık en küçük ek aktivasyon hızı veya ne kadar zaman yavaşlatması gerektiği ve sonucun parametrelere duyarlılığıdır.

İlk grafiklerde aynı koşul için bağımsız ve zamana bağlı sonuçlar, tork hatası-zaman eğrisi ve aktivasyon değişimi sınırları gösterilecek. Rastgele tohum tekrarları insan örneklem büyüklüğü sayılmayacak. Çoklu kayıtlarda kayıt/katılımcı düzeyinde tekrarlar raporlanacak.

## Aşamalı iş planı

| Aşama | İş | Çıkış koşulu |
| --- | --- | --- |
| Başlangıç | D diski ortamı, kaynak sürümleri, sentetik LP, XML/NPZ denetimi | Sentetik beklenen durumlar geçer, model derlenir ve referans alanları okunur |
| İlk hafta | Kontrolcü uyumu veya dış yüklü referans, koordinat ve tork denetimi | Normal adımın tork dengesi ve temas verileri doğrulanır |
| İkinci hafta | Tekli ve ikili kas grupları, bağımsız ve zamana bağlı çözüm | En az bir aday kombinasyon veya gerekçeli olumsuz sonuç |
| Sonraki 2–4 hafta | Aktivasyon modeli, zaman çözünürlüğü, başlangıç, kuvvet ve tendon duyarlılığı | Sayısal sorunlardan ayrışan mekanizma |
| 2–3 ay | Bağımsız kayıtlar ve ikinci model, daha kapsamlı literatür | Genellenebilirliğin sınırları ve özgün katkı açık |
| Sonraki dönem | Makale, tekrar üretim paketi ve uygun dergi seçimi | Gerçek sonuçlara göre devam kararı |

Süreler çalışma tahminidir. Hazır kontrolcü ile sürüm uyuşmazlığı veya dış yük eksikliği referans oluşturma aşamasını uzatabilir.

## Devam veya yön değiştirme kararı

Devam için tekli kayıplar telafi edilirken ikili kayıpta bağımsız kapasite yeterli olmalı. Zamana bağlı fark, açıklanabilir bir geçişte ve parametre değişimlerinde korunmalı. Fark yalnızca tam kas silmede, belirli bir kontrolcüde veya yapay hız sınırında ortaya çıkarsa mevcut bilimsel iddia daraltılır. Başlangıçta bile referans torkları karşılanamıyorsa veri ve model uyumu çözülmeden zayıflık deneyleri yorumlanmaz.

## Yayın değerlendirmesi

Şu an özgünlük adayı ve sayısal başlangıç örneği var. Tek yürüyüşte iki kas grubunu kapatma düşük yayın katkısı taşır. Güçlü sonuç, hangi kapasite kayıplarının yalnızca zaman kısıtı altında neden başarısız olduğunu açıklayan, başka kayıtlarda tekrarlanan ve mevcut statik/dinamik yöntemlerle karşılaştırılan bir yöntemdir. Q1 kabul olasılığına sayısal yüzde vermek için dayanak bulunmuyor.
