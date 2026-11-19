# Kas kapasitesi kaybında yürüyüşün zamansal uygulanabilirliği

Bu çalışma, tek tek telafi edilen kas grubu zayıflıklarının birlikte olduğunda belirli bir referans adımı hangi koşullarda sürdürülemez hâle getirdiğini araştırır. Ana hipotez, her an için yeterli tork kapasitesi bulunmasına rağmen aktivasyonun etkinleşme ve gevşeme sürelerinin adım boyunca kesintisiz bir çözümü engelleyebilmesidir.

18 Kasım 2026 tarihinde proje planı ve ilk hesaplamalar başlatıldı. Güncel çalıştırma sonuçları [DURUM.md](DURUM.md) içinde tutulur. Bilimsel protokol [ARASTIRMA_PLANI.md](ARASTIRMA_PLANI.md), kaynakların bulguları ve özgünlük sınırı [LITERATUR.md](LITERATUR.md) içindedir.

## Çalışma alanı

Bütün proje yazımları D:\projefikri\kas_animasyon altında yapılır. `.runtime` geçici dosya ve önbellekleri, `.venv` paketleri, `vendor` indirilen kaynakları, `results` hesaplama çıktılarını tutar. Her komuttan önce `scripts/environment.ps1` yüklenir. Mevcut Python ve uv yürütücüleri C diskinden okunabilir, proje ortamı ve paket kurulumları D diskine yazılır. İşletim sistemi ve uygulamanın kendi arka plan yazımları bu scriptin denetimi dışındadır.

## Çalıştırma

Güncel yerel ortam `.venv312` içindeki Python 3.12.13'tür. Normal yürüyüş tamamlandı ve ilk gerçek model sonuçları [ILK_SONUCLAR.md](ILK_SONUCLAR.md) içine kaydedildi.

Kaydedilmiş normal yürüyüşü görmek için **Yuruyusu_Izle.cmd** dosyasına çift tıklayın. Bu dosya, yerel MuJoCo penceresinde doğrulanmış kaydı döngüyle oynatır. Kapatmak için pencereyi kapatın. Video sürümü `results/baseline/normal_walk.mp4` içinde.

Kalça kaslarının tek tek ve birlikte zayıflığını (gluteus medius ve maximus, %20) dört panelde görmek için **Kalca_Kaslarini_Goster.cmd** dosyasına çift tıklayın. Video `results/visual_gluteus/gluteus_comparison.mp4` içinde.

Normal ve zayıf (sağ tibialis anterior %40) yürüyüşü yan yana görmek için **Kas_Zayifligini_Goster.cmd** dosyasına çift tıklayın. Videolar `results/visual_comparison` içinde.

Yerel Windows uygulaması için **Kas_Modelini_Ac.cmd** dosyasına çift tıklayın. MuJoCo 3.17.0, projedeki alt gövde modelini açar. Bu uygulama `programs/mujoco-3.17.0/bin/simulate.exe` konumunda. Model yerel motorla derlendi ve masaüstü penceresi açılarak kontrol edildi. Space tuşu simülasyonu durdurur veya sürdürür. Bu aşama modelin etkileşimli görüntülenmesidir. Yürüyüş kontrolcüsü daha sonra bağlanacak.

Windows'ta Akıllı Uygulama Denetimi engeline alternatif uzak çalışma için `ilk_model_deneyi_colab.ipynb` hazırlandı. Google Colab'da Dosya > Not defteri yükle ile açıp Google tarafından sağlanan CPU ortamında çalıştırılabilir. Notebook model derlemesini, kaynak sürümlerini ve ilk sentetik örneği kontrol eder. Bu dosyanın JSON yapısı ve kod hücrelerinin Python sözdizimi denetlendi. Colab üzerinde yürütme henüz doğrulanmadı. Sonuç arşivi indirilirken D:\projefikri\kas_animasyon seçilmeli. Paket ve model indirmeleri Colab'ın uzak çalışma ortamında yapılır.

PowerShell içinde proje kökünden çalıştırın.

```powershell
. .\scripts\environment.ps1
.venv312\Scripts\python.exe scripts\synthetic_pilot.py
.venv312\Scripts\python.exe scripts\audit_model.py
.venv312\Scripts\python.exe scripts\test_temporal_analysis.py
```

Mevcut ortam kuruludur; yeniden kurulum gerekmez. Aşağıdaki komutlar Python ortamını ve çalışma paketlerini D altında yeniden oluşturmak içindir. `fetch_sources.py` mevcut bir kaynak manifesti varsa yeniden indirmeyi durdurur.

```powershell
uv python install 3.12
uv venv --python 3.12 .venv312
uv pip install --python .venv312\Scripts\python.exe --only-binary :all: -r requirements-runtime.txt
.venv312\Scripts\python.exe scripts\fetch_sources.py
```

Kurulan paket sürümleri `requirements-lock.txt`, kaynak commit ve arşiv sağlama toplamları `vendor/sources.json` içinde kayıt altına alınır.

## İlk teslimler

- Sentetik örnek, kuvvet kapasitesi ile zaman sınırı karşılaştırmasının sayısal kontrolünü yapar.
- Model denetimi, gerçek XML'lerin derlenmesini ve yürüyüş kaydının içerik/koordinat uyumunu kontrol eder.
- Gerçek modelde kas zayıflığı sonucu, referans torklarının ve temas verilerinin doğrulanmasından sonra üretilebilir.

Özgünlük henüz kesinleşmedi. Q1 yayın kararı için gerçek modelde mekanizma, bağımsız yürüyüşlerde tekrar ve uygun literatür karşılaştırması gerekir.
