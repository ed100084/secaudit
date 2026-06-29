"""
稽核情境範本資料
19 個預設範本，分為四個類別：資安法系列、醫療特化、通用 IT、ISO
"""
from typing import List, Optional
from pydantic import BaseModel


class AuditTemplate(BaseModel):
    id: str
    name: str
    category: str                    # 資安法系列 | 醫療特化 | 通用IT | ISO
    description: str
    scope: str                       # 建議稽核範圍（預填文字）
    context: str                     # 建議稽核情境（預填文字）
    focus_areas: List[str]
    suggested_frameworks: List[str]  # framework id 清單
    responsibility_levels: List[str] # A B C D E，空串列代表適用所有等級
    estimated_questions: int


TEMPLATES: List[AuditTemplate] = [

    # ═══════════════════════════════════════════════════════
    # 資安法系列（4 個）
    # ═══════════════════════════════════════════════════════

    AuditTemplate(
        id="csma_annual",
        name="年度例行資安法合規稽核",
        category="資安法系列",
        description="依資通安全管理法及施行細則，對機關整體資安管理制度進行年度全面性合規稽核。涵蓋政策、制度、人員、技術及委外管理等面向。",
        scope="機關整體資通安全管理制度，包含資安政策、組織架構、人員訓練、系統盤點、風險評鑑、稽核機制及持續改善等作業",
        context="年度例行性資安法合規稽核。依《資通安全管理法》第 10 條規定，公務機關應定期辦理資安稽核。本次稽核重點確認機關資安政策是否完備、年度資安計畫執行情形、資安長職責落實狀況，以及各項控制措施符合機關責任等級要求之情形。",
        focus_areas=["資安政策與組織", "資安計畫執行", "人員訓練與意識", "資產盤點與風險評鑑", "稽核機制", "持續改善"],
        suggested_frameworks=["csma_core", "csma_classification", "csma_incident"],
        responsibility_levels=["A", "B", "C", "D", "E"],
        estimated_questions=25,
    ),

    AuditTemplate(
        id="csma_incident",
        name="資安事件通報與應變機制稽核",
        category="資安法系列",
        description="專注於資安事件通報與應變辦法之落實情形，重點查核 1 小時通報 SLA、事件分級判斷、應變程序啟動與後續改善機制。",
        scope="資安事件通報作業程序、事件應變小組運作機制、通報時效管控、事件分級判斷流程及復原程序",
        context="依《資通安全事件通報及應變辦法》第 3 條，機關應建立資安事件通報及應變機制。本次稽核查核機關是否建立符合法規要求之通報 SOP，1 小時通報 SLA 是否可達成，事件分級（P1～P4）判斷標準是否明確，以及過去一年內事件處理案例之合規性。",
        focus_areas=["通報時效（1 小時 SLA）", "事件分級判斷", "應變程序啟動", "主管機關通報", "事後檢討與改善", "演練紀錄"],
        suggested_frameworks=["csma_core", "csma_incident"],
        responsibility_levels=["A", "B", "C"],
        estimated_questions=18,
    ),

    AuditTemplate(
        id="csma_outsourcing",
        name="資通系統委外安全管理稽核",
        category="資安法系列",
        description="查核機關將資通系統或服務委外時，對廠商資安管理能力之要求、合約約定及監督機制是否符合資安法委外管理規定。",
        scope="資通系統委外採購流程、廠商資安能力評估機制、委外合約資安條款、廠商履約監督及委外系統驗收作業",
        context="依《資通安全管理法》第 15 條，機關委外辦理資通系統應要求廠商符合一定資安標準。本次稽核查核委外招標文件是否載明資安要求、廠商是否具備 ISO 27001 或等同認證、合約是否包含資安事件通報義務、以及機關對委外廠商之日常監督機制完整性。",
        focus_areas=["委外招標資安需求", "廠商資安能力審查", "委外合約資安條款", "廠商日常監督", "系統驗收資安檢測", "委外合約終止與資料返還"],
        suggested_frameworks=["csma_core", "csma_classification"],
        responsibility_levels=["A", "B", "C"],
        estimated_questions=20,
    ),

    AuditTemplate(
        id="csma_classification",
        name="資安責任等級控制要求稽核",
        category="資安法系列",
        description="針對機關責任等級（A～E 級）所應落實之技術、管理及人員控制措施進行專項稽核，確認等級適用控制措施之完整執行。",
        scope="依機關責任等級應履行之所有技術控制（滲透測試、弱點掃描、SOC 監控）、管理控制及人員控制措施",
        context="依《資通安全責任等級分級辦法》，各等級機關應落實特定控制措施。本次稽核重點確認機關依其責任等級應執行之定期滲透測試、弱點掃描作業是否按時辦理並追蹤改善，資安專責人員配置是否符合規定，以及 A/B 級機關之資安監控中心（SOC）建置或委外監控機制是否到位。",
        focus_areas=["技術控制措施落實", "管理控制措施落實", "人員資安教育訓練時數", "滲透測試與弱點掃描", "SOC 監控機制", "等級審查與申報"],
        suggested_frameworks=["csma_core", "csma_classification"],
        responsibility_levels=["A", "B", "C", "D", "E"],
        estimated_questions=22,
    ),

    # ═══════════════════════════════════════════════════════
    # 醫療特化（5 個）
    # ═══════════════════════════════════════════════════════

    AuditTemplate(
        id="health_his",
        name="醫療資訊系統（HIS/PACS/LIS）安全稽核",
        category="醫療特化",
        description="針對醫院核心臨床資訊系統的資安控制措施進行稽核，涵蓋 HIS（醫院資訊系統）、PACS（醫學影像）、LIS（檢驗資訊）等系統的存取控制、資料完整性及可用性保護。",
        scope="醫院資訊系統（HIS）、醫學影像儲傳系統（PACS）、檢驗資訊系統（LIS）、藥局系統及其整合介面的資安控制措施",
        context="本次稽核針對醫院核心臨床資訊系統進行資安查核，重點確認各系統的存取控制機制（角色權限分離、最小權限原則）、PHI（受保護健康資訊）的加密傳輸與儲存、系統可用性保護（RTO/RPO 目標）、以及系統整合介面（HL7/FHIR）的安全設定。同時查核是否符合衛福部資通安全相關規範及個人資料保護法要求。",
        focus_areas=["存取控制與帳號管理", "PHI 資料保護", "系統可用性（RTO/RPO）", "稽核日誌", "整合介面安全", "資料備份與復原"],
        suggested_frameworks=["csma_core", "csma_classification", "iso27001"],
        responsibility_levels=["A", "B"],
        estimated_questions=24,
    ),

    AuditTemplate(
        id="health_emr",
        name="電子病歷與個人健康資料保護稽核",
        category="醫療特化",
        description="查核電子病歷系統及病患個人健康資料之蒐集、處理、利用符合個資法、醫療法及衛福部電子病歷相關規範，重點查核病患同意機制、資料最小化及跨機構傳輸安全。",
        scope="電子病歷系統（EMR）、病患個人健康資料蒐集處理流程、病歷調閱授權機制、跨院資料交換及病患知情同意作業",
        context="依《醫療法》第 67 條及《個人資料保護法》規定，醫療機構蒐集利用病患健康資料應取得同意並妥善保護。本次稽核查核電子病歷存取授權機制、病歷調閱記錄的完整性、病患健康資料境外傳輸控制，以及醫療人員存取病患資料之最小必要原則落實情形。",
        focus_areas=["病患同意機制", "病歷調閱授權與記錄", "健康資料最小化", "跨機構安全傳輸", "資料保存年限管理", "違規存取偵測"],
        suggested_frameworks=["csma_core", "iso27001", "iso27701"],
        responsibility_levels=["A", "B"],
        estimated_questions=20,
    ),

    AuditTemplate(
        id="health_iomt",
        name="醫療物聯網（IoMT）資安稽核",
        category="醫療特化",
        description="針對醫院聯網醫療設備（心電監測器、點滴幫浦、呼吸器等）進行資安稽核，查核設備識別、網路隔離、韌體更新管理及設備異常行為偵測。",
        scope="醫院內所有聯網醫療設備（IoMT）、設備管理平台、設備專屬網路分段及醫療設備資安生命週期管理作業",
        context="醫療物聯網設備（IoMT）因直接關係病患安危，資安風險極高。本次稽核查核醫院是否建立完整的 IoMT 設備清冊、是否落實網路分段隔離（設備 VLAN 與臨床網路分離）、設備韌體是否定期更新及漏洞修補、是否有設備行為異常偵測機制，並確認高風險設備（如生命維持設備）的實體安全措施。",
        focus_areas=["設備清冊與識別", "網路分段與隔離", "韌體更新管理", "設備漏洞管理", "異常行為偵測", "設備實體安全"],
        suggested_frameworks=["csma_core", "iso27001"],
        responsibility_levels=["A", "B"],
        estimated_questions=18,
    ),

    AuditTemplate(
        id="health_telehealth",
        name="遠距醫療與視訊診療安全稽核",
        category="醫療特化",
        description="查核遠距照護及視訊診療平台的資安控制措施，包含病患身份驗證、診療資料傳輸加密、平台資安認證及跨平台資料整合安全。",
        scope="視訊診療平台、遠距照護系統、病患端 App、診療資料傳輸通道及遠距照護資料與 HIS 整合介面",
        context="疫情後遠距醫療蓬勃發展，依衛福部遠距醫療相關規範，視訊診療平台應具備一定資安標準。本次稽核查核平台的病患身份驗證強度（是否支援多因子驗證）、診療過程影音資料的加密與儲存政策、平台是否取得相關資安認證、以及病患端 App 的資安設計（證書固定、本地儲存加密）。",
        focus_areas=["病患身份驗證", "診療資料加密傳輸", "平台資安認證", "App 資安設計", "診療紀錄保存", "跨平台整合安全"],
        suggested_frameworks=["csma_core", "iso27001", "iso27701"],
        responsibility_levels=["A", "B"],
        estimated_questions=16,
    ),

    AuditTemplate(
        id="health_supply_chain",
        name="醫療供應鏈資安稽核",
        category="醫療特化",
        description="查核醫院與藥品、耗材及醫療器械供應商之資安管理，包含供應商資安評估、採購系統安全、庫存管理系統資安及供應鏈資料完整性。",
        scope="醫院採購系統、庫存管理系統、與供應商之 EDI/API 介面、藥品智慧調配設備及供應商資安管理機制",
        context="醫療供應鏈涉及藥品調配與耗材管理，任何資安事件可能直接影響病患安全。本次稽核查核醫院採購及庫存系統的存取控制、與供應商電子訂單介面（EDI/API）的安全認證與傳輸加密、藥品智慧調配機（ADC）的網路安全設定、以及供應商資安事件通報義務的合約約定。",
        focus_areas=["採購系統存取控制", "供應商 EDI/API 安全", "藥品調配設備安全", "庫存資料完整性", "供應商資安評估", "供應鏈事件應變"],
        suggested_frameworks=["csma_core", "csma_classification"],
        responsibility_levels=["A", "B"],
        estimated_questions=16,
    ),

    # ═══════════════════════════════════════════════════════
    # 通用 IT（8 個）
    # ═══════════════════════════════════════════════════════

    AuditTemplate(
        id="it_access_control",
        name="存取控制與帳號管理稽核",
        category="通用IT",
        description="查核機關/機構的身份識別、認證、授權及帳號生命週期管理，重點確認最小權限原則、特殊帳號管控及閒置帳號清理機制。",
        scope="作業系統、應用系統、資料庫及網路設備的帳號管理作業，包含 AD/LDAP 目錄服務、權限審查流程及特殊帳號管控",
        context="存取控制是資安基礎控制措施之一。本次稽核查核各系統帳號是否定期審查、離職人員帳號是否及時停用、特殊帳號（系統管理員、服務帳號、共用帳號）是否有額外管控措施、密碼政策是否符合最低強度要求，以及是否部署多因子驗證（MFA）於高風險系統。",
        focus_areas=["帳號生命週期管理", "最小權限原則", "特殊帳號管控", "密碼政策", "多因子驗證（MFA）", "閒置帳號審查"],
        suggested_frameworks=["csma_core", "iso27001"],
        responsibility_levels=[],
        estimated_questions=20,
    ),

    AuditTemplate(
        id="it_network_security",
        name="網路架構與邊界安全稽核",
        category="通用IT",
        description="查核網路分段設計、防火牆規則、DMZ 架構、遠端存取安全及網路監控機制，確保邊界防禦符合縱深防禦原則。",
        scope="網路拓撲設計（分段/分區）、防火牆與 ACL 規則管理、VPN/遠端存取、IDS/IPS 部署及網路流量監控",
        context="縱深防禦需要完善的網路邊界安全設計。本次稽核查核核心網路分段是否落實（生產/開發/管理網路隔離）、防火牆規則是否定期審查並移除冗餘規則、遠端存取是否強制使用 VPN 加 MFA、外部攻擊面是否定期盤點，以及是否有 IDS/IPS 或 NDR 工具進行網路威脅偵測。",
        focus_areas=["網路分段設計", "防火牆規則管理", "遠端存取安全", "IDS/IPS 部署", "外部攻擊面管理", "無線網路安全"],
        suggested_frameworks=["csma_core", "iso27001"],
        responsibility_levels=[],
        estimated_questions=18,
    ),

    AuditTemplate(
        id="it_backup_recovery",
        name="資料備份與災難復原稽核",
        category="通用IT",
        description="查核備份作業的完整性、備份資料的可用性測試、離線備份機制及災難復原計畫（DRP）的制定與演練，確保 RTO/RPO 目標可達成。",
        scope="關鍵系統備份作業程序、備份資料儲存（含異地及離線備份）、備份還原測試紀錄及災難復原計畫（DRP）",
        context="勒索軟體攻擊造成備份失效的案例日益增多，備份安全至關重要。本次稽核查核是否落實 3-2-1 備份原則、備份資料是否定期執行還原測試（測試成功率及時間）、是否保有離線或不可更改備份（immutable backup）防範勒索軟體、DRP 是否訂定明確 RTO/RPO 目標，以及最近一次全規模演練的結果。",
        focus_areas=["備份完整性與頻率", "3-2-1 備份原則", "離線/不可更改備份", "備份還原測試", "DRP 制定與維護", "RTO/RPO 目標達成"],
        suggested_frameworks=["csma_core", "iso27001"],
        responsibility_levels=[],
        estimated_questions=16,
    ),

    AuditTemplate(
        id="it_vulnerability_mgmt",
        name="弱點管理與修補作業稽核",
        category="通用IT",
        description="查核弱點掃描執行頻率與覆蓋範圍、高危弱點修補時效、例外申請管理及弱點管理程序的完整性。",
        scope="作業系統、應用程式、網路設備及雲端環境的弱點掃描作業、CVE 修補追蹤管理及例外處理程序",
        context="弱點管理是預防性資安的核心。本次稽核查核弱點掃描是否涵蓋所有資產（含雲端）、高危（CVSS ≥ 7.0）弱點是否在 30 天內修補、零日漏洞緊急應變程序是否明確、例外申請流程是否有適當審批與補償控制，以及修補完成率統計與趨勢分析是否定期呈報管理階層。",
        focus_areas=["掃描頻率與覆蓋範圍", "高危弱點修補時效", "零日漏洞應變", "例外處理程序", "修補完成率追蹤", "第三方元件管理"],
        suggested_frameworks=["csma_core", "csma_classification", "iso27001"],
        responsibility_levels=[],
        estimated_questions=18,
    ),

    AuditTemplate(
        id="it_privileged_access",
        name="特權帳號與特殊存取管理稽核",
        category="通用IT",
        description="專項查核系統管理員、DBA、網路工程師等特權帳號的使用管控，包含特權存取工作站（PAW）、Just-in-Time 存取及特權操作稽核日誌。",
        scope="所有特權帳號（系統管理員、DBA、網路管理員、服務帳號）的識別、授權、使用監控及特權操作稽核日誌",
        context="特權帳號遭濫用是重大資安事件的主要原因之一。本次稽核查核特權帳號清冊是否完整、是否落實職責分離（同一人不得同時擁有開發與生產環境特權）、特權操作是否全程記錄並受監控、是否部署特權存取管理（PAM）工具進行密碼保險庫及 Session 錄製，以及定期帳號審查機制。",
        focus_areas=["特權帳號清冊", "職責分離", "特權操作稽核日誌", "PAM 工具部署", "緊急存取程序", "服務帳號管控"],
        suggested_frameworks=["csma_core", "iso27001"],
        responsibility_levels=[],
        estimated_questions=16,
    ),

    AuditTemplate(
        id="it_security_awareness",
        name="資安意識與社交工程防禦稽核",
        category="通用IT",
        description="查核員工資安教育訓練計畫、釣魚演練機制、安全意識指標追蹤及高風險族群（管理層、財務人員）的強化訓練落實情形。",
        scope="年度資安教育訓練計畫、釣魚郵件演練紀錄、訓練完成率統計、高風險族群訓練及資安意識測量指標",
        context="人員是最常被利用的資安弱點。本次稽核查核年度資安訓練課程是否符合責任等級規定時數（A/B 級 12 小時以上）、釣魚演練是否定期執行並追蹤改善、是否針對高風險族群（C-Suite、財務、HR）辦理進階訓練、以及近兩年點擊率趨勢是否改善。同時查核新進人員資安宣導落實情形。",
        focus_areas=["訓練時數與完成率", "釣魚演練頻率與改善", "高風險族群訓練", "新進人員資安宣導", "意識測量指標", "訓練成效評估"],
        suggested_frameworks=["csma_core", "csma_classification"],
        responsibility_levels=[],
        estimated_questions=14,
    ),

    AuditTemplate(
        id="it_cloud_security",
        name="雲端服務安全管理稽核",
        category="通用IT",
        description="查核機關/機構使用公有雲（AWS/Azure/GCP）或 SaaS 服務的安全管理，包含雲端安全基準設定、身份管理（IAM）及共同責任模型落實。",
        scope="公有雲環境安全設定（CSP 安全基準）、雲端 IAM 管理、儲存加密設定、網路安全群組規則及雲端資安監控",
        context="雲端設定錯誤（misconfiguration）是目前最常見的雲端資安事件來源。本次稽核查核雲端環境是否套用 CIS Benchmark 或 CSP 安全基準、IAM 角色是否遵循最小權限、S3/Blob 等物件儲存是否關閉公開存取、CloudTrail/Log Analytics 是否啟用並整合 SIEM、以及是否部署 CSPM（雲端安全態勢管理）工具持續偵測錯誤設定。",
        focus_areas=["雲端安全基準設定", "IAM 最小權限", "資料加密（靜態/傳輸）", "雲端日誌與監控", "CSPM 工具部署", "SaaS 應用清冊管理"],
        suggested_frameworks=["csma_core", "iso27001"],
        responsibility_levels=[],
        estimated_questions=20,
    ),

    AuditTemplate(
        id="it_incident_drill",
        name="資安事件應變演練效能稽核",
        category="通用IT",
        description="查核資安事件應變計畫（IRP）的制定品質、桌上演練（TTX）或全規模演練的執行情形，以及演練後改善追蹤的落實程度。",
        scope="資安事件應變計畫（IRP）文件、年度演練執行紀錄、演練缺失改善追蹤、應變小組成員訓練及外部資源聯繫機制",
        context="資安應變能力必須透過演練驗證。本次稽核查核 IRP 是否完整涵蓋各事件類型（勒索軟體、DDoS、資料外洩）、今年是否已辦理至少一次桌上演練（TTX）或全規模演練、演練發現缺失是否有改善計畫並追蹤完成、應變小組成員是否定期輪訓，以及外部資源（CERT、律師、PR）聯絡清單是否維護更新。",
        focus_areas=["IRP 完整性", "演練頻率與規模", "演練缺失改善追蹤", "應變小組訓練", "外部資源聯繫", "業務復原優先序"],
        suggested_frameworks=["csma_core", "csma_incident", "iso27001"],
        responsibility_levels=[],
        estimated_questions=16,
    ),

    # ═══════════════════════════════════════════════════════
    # ISO（2 個）
    # ═══════════════════════════════════════════════════════

    AuditTemplate(
        id="iso27001_audit",
        name="ISO 27001:2022 導入合規稽核",
        category="ISO",
        description="依 ISO 27001:2022 標準，查核 ISMS 管理系統的建立、實作、維護及持續改善，包含 Annex A 93 項控制措施的適用性聲明（SoA）執行情形。",
        scope="ISO 27001:2022 資訊安全管理系統（ISMS）全系統，包含管理審查、內部稽核、風險評鑑程序及 Annex A 適用性聲明（SoA）",
        context="本次稽核為 ISO 27001:2022 ISMS 內部稽核或導入前評估。重點查核 ISMS 範圍界定是否明確、風險評鑑方法論是否一致適用、SoA 中排除控制措施之理由是否充分、控制措施有效性是否可量測，以及管理審查記錄是否呈現持續改善趨勢。特別關注 2022 版新增的 11 項控制措施（威脅情報、ICT 供應鏈等）的落實情形。",
        focus_areas=["ISMS 範圍界定", "風險評鑑與處理", "適用性聲明（SoA）", "管理審查", "內部稽核計畫", "2022 版新增控制措施"],
        suggested_frameworks=["iso27001", "csma_core"],
        responsibility_levels=[],
        estimated_questions=28,
    ),

    AuditTemplate(
        id="iso27701_audit",
        name="ISO 27701:2025 隱私管理稽核",
        category="ISO",
        description="依 ISO 27701:2025 標準，查核隱私資訊管理系統（PIMS）的建立情形，包含個資保護衝擊評估（DPIA）、資料主體權利回應及個資外洩應變。",
        scope="隱私資訊管理系統（PIMS）、個人資料蒐集處理利用流程、DPIA 執行情形、資料主體權利行使機制及個資保護長（DPO）職能",
        context="ISO 27701 是 ISO 27001 的隱私擴展，也是符合個資法及 GDPR 的參考框架。本次稽核查核 PIMS 是否整合至現有 ISMS 運作、隱私注意事項（Privacy by Design）是否融入系統開發流程、DPIA 是否於高風險處理前執行、資料主體要求（查詢、更正、刪除）的回應時效是否符合法規要求，以及個資外洩的偵測、評估及通報機制完整性。",
        focus_areas=["PIMS 整合建置", "個資盤點與流程圖", "DPIA 執行", "Privacy by Design", "資料主體權利回應", "個資外洩應變"],
        suggested_frameworks=["iso27701", "iso27001", "csma_core"],
        responsibility_levels=[],
        estimated_questions=22,
    ),
]

# 快速查詢字典
_TEMPLATE_MAP = {t.id: t for t in TEMPLATES}


def get_all_templates() -> List[AuditTemplate]:
    return TEMPLATES


def get_template(template_id: str) -> Optional[AuditTemplate]:
    return _TEMPLATE_MAP.get(template_id)


def get_templates_by_category(category: str) -> List[AuditTemplate]:
    return [t for t in TEMPLATES if t.category == category]
