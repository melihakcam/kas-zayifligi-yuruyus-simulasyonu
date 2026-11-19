# Yakın literatür ve özgünlük kaydı

Bu kayıt 15–18 Kasım 2026 oturumlarındaki hedefli taramayı derler. Makalelerin incelenen yöntem/deney bölümleri özetlenmiştir. Kapsamlı sistematik derleme veya kesin ilk çalışma beyanı içermez. Arşivlenmiş bir arama veritabanı çıktısı henüz oluşturulmadı.

## En yakın çalışmalar

| Çalışma | Doğrulanan katkı ve projemizle ilişkisi |
| --- | --- |
| Yamaguchi ve Zajac, 1990 | Dinamik programlama ve ileri simülasyonla bir adımı sağlayan az sayıda kas ve uyarı zamanlaması arandı. En az kasla adım üretme fikri eski. [Tam metin](https://www.cs.cmu.edu/~cga/behavior/yamaguchi.pdf), özellikle yöntem B ve C. [DOI](https://doi.org/10.1109/10.58599) |
| Anderson ve Pandy, 2001 | Normal yürüyüşte statik ve dinamik optimizasyon çözümleri karşılaştırıldı. Zaman dinamiğini eklemenin her koşulda büyük fark ürettiği varsayılamaz. [Yayıncı](https://www.sciencedirect.com/science/article/pii/S002192900000155X) |
| Van der Krogt ve ark., 2012 | Kas grupları ayrı ayrı ve genel zayıflıkla azaltılarak normal yürüyüşün ne kadar korunabildiği incelendi. Zayıflık eşiği ve telafi yeni değil. [Makale](https://pmc.ncbi.nlm.nih.gov/articles/PMC4890623/), bazı erişimlerde CAPTCHA görüldü. |
| Simpson ve ark., 2015 | Yürüyüşte her an bağımsız optimizasyonla mümkün kas aktivasyonu aralıkları hesaplandı. Zamana bağlanan çözümün karşılaştırılacağı yakın yaklaşım. [Tam metin](https://pmc.ncbi.nlm.nih.gov/articles/PMC4592831/) |
| Sohn, Smith ve Ting, 2019 | Model karmaşıklığı ve tek kas kaybının mümkün kuvvet bölgelerine etkisini inceledi. Kas sayısı fazla olduğunda otomatik dayanıklılık sonucu çıkarılamaz. [Tam metin](https://pmc.ncbi.nlm.nih.gov/articles/PMC6655685/) |
| Spomer ve ark., 2022 | Kas sinerjisi sayısının zayıflık ve kontraktür altında yürüyüşün sürdürülme eşiklerine etkisini dinamik izleme simülasyonuyla ölçtü. Kontrol kısıtları ve zayıflık etkileşimi zaten ele alınmış. [Tam metin](https://pmc.ncbi.nlm.nih.gov/articles/PMC8976766/) |
| Cohn ve Valero-Cuevas, 2023 | Yedi kaslı parmak modelinde 300 ms kuvvet dizisini zaman kısıtlarıyla bağlayan genişletilmiş LP kullandı. Zaman kısıtının mümkün kas çözümlerini daraltması bizim temel hipotezimizin yakın öncülüdür. [Tam metin](https://pmc.ncbi.nlm.nih.gov/articles/PMC10663283/), DOI 10.3389/fresc.2023.1248269. |
| Kuska ve Steele, 2024 | Normal ve çömelerek yürüyüşte zayıflık, kontraktür ve kontrol karmaşıklığının etkilerini karşılaştırdı. [Kayıt](https://pubmed.ncbi.nlm.nih.gov/38394953/), [DOI](https://doi.org/10.1016/j.jbiomech.2024.112015). PMC erişimi bazı denemelerde CAPTCHA döndürdü. |
| Buchmann ve ark., 2025 | VAS, GAS ve HAM kas uyarılarının farklı yürüyüş fazlarında kesilmesinin diz ve ayak bileği itişine etkisini inceledi. Kas kapatma fazı ve süre taraması zaten yapılmış. [Tam metin](https://doi.org/10.1038/s41598-025-86147-z) |
| Bosch Van Den ve ark., 2025 | Kas zayıflığı, kontraktür ve kemik geometrisi bozukluklarının birlikte etkisini hasta verilerine dayalı modellerle, Shapley değerleriyle değerlendirdi. Birleşik bozukluk etkisi tek başına yenilik değildir. [Tam metin](https://doi.org/10.1186/s12984-025-01767-w) |
| 2026 oturmadan yürümeye geçiş çalışması | Kuadriseps zayıflığı ve sinirsel gecikmenin kayma altında birlikte etkisini 5×5 taramayla araştırdı. Ayrı ayrı telafi edilen sorunların birlikte başarısızlık vermesi fikrinin yakın komşusudur. Aktivasyon zaman sabiti ile sinirsel iletim gecikmesi ayrı mekanizmalardır. [PubMed ve özet](https://pubmed.ncbi.nlm.nih.gov/42172877/). Bu oturumlarda tam yöntem bağımsız olarak okunmadı. |
| Afschrift ve ark., 2025 | Yürüyüş simülasyonlarının birden fazla deney koşulunda doğrulanmasında belirgin model sınırlılıkları saptadı. Model sonucu insan fizyolojisine taşınırken bağımsız doğrulama gerekir. [Tam metin](https://pmc.ncbi.nlm.nih.gov/articles/PMC12622833/) |

## Açık kalan iddia

Sabit referans hareket ve dış yükler altında, tüm tekli kayıplar telafi edilirken en küçük birleşik grup kaybında bağımsız zaman noktaları mümkün kalsın, aktivasyonun fizyolojik geçiş kısıtları eklendiğinde tüm adımın çözümü kaybolsun. Bu koşulları birlikte ve minimum kayıp kümesini arayarak ele alan bir yürüyüş makalesi hedefli taramada bulunamadı. Bu ifade, ilgili bütün yayınların elendiği anlamına gelmez.

Elektrik şebekelerinde N−k yaklaşımı en küçük bozucu birleşimi aramak için yöntemsel ilhamdır. Kaslar pozitif kuvvet üreten, zaman bağımlı ve anatomik olarak bağlı aktüatörlerdir. Şebeke akış denklemleri doğrudan kaslara uygulanamaz. [Bienstock ve Verma](https://arxiv.org/abs/0912.5233).

## Sürdürülecek tarama

- `gait minimum muscle failure combination activation contraction dynamics feasibility`
- `musculoskeletal pointwise feasible dynamic infeasible muscle weakness`
- `minimal disabling muscle set fixed gait temporal activation constraints`
- `muscle loss combinations feasible force set simultaneous dysfunction`
- `minimum muscles functional neuromuscular stimulation dynamic programming gait`
- Cohn 2023 ve Van der Krogt 2012 için ileri/geri atıf taraması.
- FES kas seçimi, aktüatör kaybı ve kontrol tahsisi literatüründe eşdeğer sorular.

## Repo kaynakları ve lisans

[MS-Human-700](https://github.com/LNSGroup/MS-Human-700), [msgym](https://github.com/LNSGroup/msgym), [kontrolcü sürümü](https://github.com/LNSGroup/msgym/releases/tag/Checkpoints). İndirilen commitler ve SHA256 değerleri `vendor/sources.json` içinde tutulur. Depoların LICENSE dosyaları kaynaklarla birlikte saklanır. Referans hareketin kökeni ve yeniden dağıtım koşulları ayrıca incelenecek.
