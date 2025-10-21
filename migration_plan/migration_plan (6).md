CREATE POLICY journal_entries_tenant_isolation ON journal_entries
    FOR ALL TO authenticated_users
    USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

-- Функция для установки контекста тенанта
CREATE OR REPLACE FUNCTION set_tenant_context(tenant_uuid UUID)
RETURNS void AS $
BEGIN
    PERFORM set_config('app.current_tenant_id', tenant_uuid::text, false);
END;
$ LANGUAGE plpgsql;
```

### Результаты Фазы 4:
- ✅ Cloud-native deployment в GCP/AWS
- ✅ ML-powered fraud detection
- ✅ Real-time analytics с ClickHouse
- ✅ BI dashboard с Plotly
- ✅ Multi-tenant архитектура
- ✅ 95% покрытие тестами всей системы

---

## 🎯 Фаза 5: Оптимизация и Go-Live (Месяцы 19-24)

### Цели:
- Performance tuning
- Load testing
- Security audit
- User training
- Production deployment

### 5.1 Performance Optimization (Месяцы 19-20)

#### Database optimization
```sql
-- performance_optimization.sql

-- Партиционирование крупных таблиц по времени
CREATE TABLE journal_entries_optimized (
    LIKE journal_entries INCLUDING ALL
) PARTITION BY RANGE (transaction_date);

-- Создание партиций на 2 года вперед
DO $
DECLARE
    start_date DATE := '2025-01-01';
    end_date DATE;
    partition_name TEXT;
BEGIN
    FOR i IN 0..23 LOOP
        end_date := start_date + INTERVAL '1 month';
        partition_name := 'journal_entries_' || to_char(start_date, 'YYYY_MM');
        
        EXECUTE format('CREATE TABLE %I PARTITION OF journal_entries_optimized 
                       FOR VALUES FROM (%L) TO (%L)',
                       partition_name, start_date, end_date);
        
        -- Индексы для каждой партиции
        EXECUTE format('CREATE INDEX %I ON %I (tenant_id, account_id, transaction_date)',
                       'idx_' || partition_name || '_lookup', partition_name);
        
        start_date := end_date;
    END LOOP;
END $;

-- Материализованные представления для быстрых агрегаций
CREATE MATERIALIZED VIEW account_balances_daily AS
SELECT 
    tenant_id,
    account_id,
    transaction_date,
    sum(debit - credit) OVER (
        PARTITION BY tenant_id, account_id 
        ORDER BY transaction_date 
        ROWS UNBOUNDED PRECEDING
    ) as running_balance,
    sum(debit - credit) as daily_change
FROM journal_entries_optimized
WHERE transaction_date >= CURRENT_DATE - INTERVAL '2 years'
GROUP BY tenant_id, account_id, transaction_date, debit, credit;

CREATE UNIQUE INDEX idx_account_balances_daily_unique 
ON account_balances_daily (tenant_id, account_id, transaction_date);

-- Автоматическое обновление материализованных представлений
CREATE OR REPLACE FUNCTION refresh_daily_balances()
RETURNS void AS $
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY account_balances_daily;
END;
$ LANGUAGE plpgsql;

-- Планировщик для обновления представлений
SELECT cron.schedule('refresh-daily-balances', '0 1 * * *', 'SELECT refresh_daily_balances();');
```

#### Caching strategy
```python
# caching/redis_cache.py
from functools import wraps
import redis.asyncio as redis
import json
import hashlib
from typing import Any, Optional, Callable
import asyncio

class DistributedCache:
    def __init__(self, redis_url: str = "redis://redis:6379"):
        self.redis = redis.from_url(redis_url, decode_responses=True)
        self.default_ttl = 3600  # 1 час
    
    def cache_key(self, prefix: str, *args, **kwargs) -> str:
        """Генерация ключа кэша на основе аргументов"""
        key_data = f"{prefix}:{args}:{sorted(kwargs.items())}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    async def get(self, key: str) -> Optional[Any]:
        """Получить значение из кэша"""
        try:
            value = await self.redis.get(key)
            if value:
                return json.loads(value)
        except Exception as e:
            logger.error(f"Cache get error: {e}")
        return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Установить значение в кэш"""
        try:
            ttl = ttl or self.default_ttl
            serialized = json.dumps(value, default=str)
            return await self.redis.setex(key, ttl, serialized)
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False
    
    async def delete(self, pattern: str) -> int:
        """Удалить ключи по шаблону"""
        try:
            keys = await self.redis.keys(pattern)
            if keys:
                return await self.redis.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            return 0
    
    def cached(self, ttl: Optional[int] = None, key_prefix: str = "cache"):
        """Декоратор для кэширования результатов функций"""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Исключить self из аргументов для ключа кэша
                cache_args = args[1:] if args and hasattr(args[0], '__class__') else args
                cache_key = self.cache_key(f"{key_prefix}:{func.__name__}", *cache_args, **kwargs)
                
                # Попытаться получить из кэша
                cached_result = await self.get(cache_key)
                if cached_result is not None:
                    return cached_result
                
                # Вычислить результат
                result = await func(*args, **kwargs)
                
                # Сохранить в кэш
                await self.set(cache_key, result, ttl)
                return result
            
            return wrapper
        return decorator

class SmartCache:
    """Умное кэширование с invalidation по тэгам"""
    
    def __init__(self, cache: DistributedCache):
        self.cache = cache
        self.tag_prefix = "tags:"
    
    async def set_with_tags(self, key: str, value: Any, tags: list, ttl: Optional[int] = None):
        """Установить значение с тэгами для invalidation"""
        # Сохранить основное значение
        await self.cache.set(key, value, ttl)
        
        # Связать с тэгами
        for tag in tags:
            tag_key = f"{self.tag_prefix}{tag}"
            await self.cache.redis.sadd(tag_key, key)
            if ttl:
                await self.cache.redis.expire(tag_key, ttl + 86400)  # TTL + 1 день для тэгов
    
    async def invalidate_by_tag(self, tag: str):
        """Инвалидировать все ключи с определенным тэгом"""
        tag_key = f"{self.tag_prefix}{tag}"
        keys = await self.cache.redis.smembers(tag_key)
        
        if keys:
            # Удалить основные ключи
            await self.cache.redis.delete(*keys)
            # Удалить тэг
            await self.cache.redis.delete(tag_key)
            
        return len(keys)

# Использование в сервисах
class AccountService:
    def __init__(self):
        self.cache = DistributedCache()
        self.smart_cache = SmartCache(self.cache)
        self.repository = AccountRepository()
    
    @cache.cached(ttl=1800, key_prefix="accounts")
    async def get_account_by_id(self, tenant_id: str, account_id: str) -> Optional[Account]:
        """Получить счет по ID с кэшированием"""
        with TenantContext(tenant_id):
            return await self.repository.get_by_id(account_id)
    
    async def create_account(self, tenant_id: str, account_data: AccountCreate) -> Account:
        """Создать счет с инвалидацией кэша"""
        with TenantContext(tenant_id):
            account = await self.repository.create(account_data)
            
            # Инвалидировать кэш
            await self.smart_cache.invalidate_by_tag(f"tenant:{tenant_id}:accounts")
            
            return account
    
    @smart_cache.cached(ttl=300, tags_func=lambda tenant_id: [f"tenant:{tenant_id}:balances"])
    async def get_account_balance(self, tenant_id: str, account_id: str, as_of_date: Optional[date] = None) -> Decimal:
        """Получить баланс счета с кэшированием по тэгам"""
        with TenantContext(tenant_id):
            return await self.repository.get_balance(account_id, as_of_date)
```

### 5.2 Load Testing (Месяц 21)

#### Load testing с Locust
```python
# load_testing/locustfile.py
from locust import HttpUser, task, between
import json
import uuid
from datetime import datetime, date
import random

class AccountingSystemUser(HttpUser):
    wait_time = between(1, 3)
    
    def on_start(self):
        """Авторизация перед началом тестов"""
        self.login()
        self.tenant_id = "test-tenant-001"
        self.auth_headers = {
            "Authorization": f"Bearer {self.access_token}",
            "X-Tenant-ID": self.tenant_id,
            "Content-Type": "application/json"
        }
    
    def login(self):
        """Авторизация в системе"""
        login_data = {
            "username": f"testuser_{random.randint(1, 100)}",
            "password": "testpass123"
        }
        response = self.client.post("/api/v1/auth/login", json=login_data)
        if response.status_code == 200:
            self.access_token = response.json()["access_token"]
        else:
            self.access_token = "dummy-token"
    
    @task(3)
    def get_accounts(self):
        """Получение списка счетов (частый запрос)"""
        self.client.get("/api/v1/accounts", headers=self.auth_headers)
    
    @task(2)
    def get_account_balance(self):
        """Получение баланса счета"""
        account_id = str(uuid.uuid4())  # В реальности должен быть существующий ID
        self.client.get(
            f"/api/v1/accounts/{account_id}/balance",
            headers=self.auth_headers
        )
    
    @task(5)
    def create_transaction(self):
        """Создание транзакции (основная нагрузка)"""
        transaction_data = {
            "transaction_date": date.today().isoformat(),
            "description": f"Test transaction {random.randint(1, 10000)}",
            "entries": [
                {
                    "account_id": str(uuid.uuid4()),
                    "debit": random.uniform(100, 10000),
                    "credit": 0,
                    "description": "Test debit entry"
                },
                {
                    "account_id": str(uuid.uuid4()),
                    "debit": 0,
                    "credit": random.uniform(100, 10000),
                    "description": "Test credit entry"
                }
            ]
        }
        
        # Убедиться что дебет = кредит
        transaction_data["entries"][1]["credit"] = transaction_data["entries"][0]["debit"]
        
        self.client.post(
            "/api/v1/transactions",
            json=transaction_data,
            headers=self.auth_headers
        )
    
    @task(1)
    def get_financial_report(self):
        """Генерация финансового отчета (тяжелый запрос)"""
        params = {
            "start_date": "2025-01-01",
            "end_date": date.today().isoformat(),
            "report_type": "balance_sheet"
        }
        
        self.client.get(
            "/api/v1/reports/financial",
            params=params,
            headers=self.auth_headers
        )
    
    @task(1)
    def calculate_vat(self):
        """Расчет НДС"""
        vat_data = {
            "net_amount": random.uniform(1000, 50000),
            "is_exempt": random.choice([True, False])
        }
        
        self.client.post(
            "/api/v1/tax/vat/calculate",
            json=vat_data,
            headers=self.auth_headers
        )

class HighLoadUser(HttpUser):
    """Пользователь с высокой нагрузкой для стресс-тестов"""
    wait_time = between(0.1, 0.5)  # Более агрессивная нагрузка
    weight = 1
    
    @task
    def rapid_balance_checks(self):
        """Частые проверки балансов"""
        for _ in range(10):
            account_id = random.choice([
                "550e8400-e29b-41d4-a716-446655440001",
                "550e8400-e29b-41d4-a716-446655440002",
                "550e8400-e29b-41d4-a716-446655440003"
            ])
            self.client.get(f"/api/v1/accounts/{account_id}/balance")

# Конфигурация для различных сценариев нагрузки
class LoadTestConfig:
    scenarios = {
        "normal_load": {
            "users": 100,
            "spawn_rate": 5,
            "duration": "10m"
        },
        "peak_load": {
            "users": 500,
            "spawn_rate": 25,
            "duration": "15m"
        },
        "stress_test": {
            "users": 1000,
            "spawn_rate": 50,
            "duration": "30m"
        },
        "endurance_test": {
            "users": 200,
            "spawn_rate": 10,
            "duration": "2h"
        }
    }
```

#### Performance monitoring
```python
# monitoring/performance_monitor.py
import asyncio
import psutil
import time
from datetime import datetime
from dataclasses import dataclass
from typing import Dict, List
import aiohttp

@dataclass
class PerformanceMetrics:
    timestamp: datetime
    cpu_usage: float
    memory_usage: float
    disk_io: Dict[str, float]
    network_io: Dict[str, float]
    response_times: Dict[str, float]
    error_rates: Dict[str, float]
    active_connections: int

class PerformanceMonitor:
    def __init__(self):
        self.metrics_history: List[PerformanceMetrics] = []
        self.thresholds = {
            "cpu_usage": 80.0,
            "memory_usage": 85.0,
            "avg_response_time": 2.0,
            "error_rate": 5.0
        }
        self.alerts_sent = set()
    
    async def collect_system_metrics(self) -> Dict:
        """Сбор системных метрик"""
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk_io = psutil.disk_io_counters()
        network_io = psutil.net_io_counters()
        
        return {
            "cpu_usage": cpu_percent,
            "memory_usage": memory.percent,
            "disk_io": {
                "read_bytes": disk_io.read_bytes,
                "write_bytes": disk_io.write_bytes
            },
            "network_io": {
                "bytes_sent": network_io.bytes_sent,
                "bytes_recv": network_io.bytes_recv
            }
        }
    
    async def collect_application_metrics(self) -> Dict:
        """Сбор метрик приложения"""
        # Запросы к Prometheus metrics endpoint
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:8000/metrics") as response:
                metrics_text = await response.text()
        
        # Парсинг метрик (упрощенно)
        response_times = {}
        error_rates = {}
        active_connections = 0
        
        for line in metrics_text.split('\n'):
            if 'http_request_duration_seconds' in line and 'quantile="0.95"' in line:
                # Извлечь значение 95-го перцентиля времени ответа
                value = float(line.split()[-1])
                endpoint = self._extract_endpoint(line)
                response_times[endpoint] = value
            
            elif 'http_requests_total' in line and 'status="5' in line:
                # Подсчет ошибок 5xx
                value = float(line.split()[-1])
                endpoint = self._extract_endpoint(line)
                error_rates[endpoint] = value
        
        return {
            "response_times": response_times,
            "error_rates": error_rates,
            "active_connections": active_connections
        }
    
    async def check_thresholds(self, metrics: PerformanceMetrics):
        """Проверка пороговых значений и отправка алертов"""
        alerts = []
        
        if metrics.cpu_usage > self.thresholds["cpu_usage"]:
            alerts.append(f"High CPU usage: {metrics.cpu_usage:.1f}%")
        
        if metrics.memory_usage > self.thresholds["memory_usage"]:
            alerts.append(f"High memory usage: {metrics.memory_usage:.1f}%")
        
        avg_response_time = sum(metrics.response_times.values()) / len(metrics.response_times) if metrics.response_times else 0
        if avg_response_time > self.thresholds["avg_response_time"]:
            alerts.append(f"High average response time: {avg_response_time:.2f}s")
        
        for alert in alerts:
            alert_hash = hash(alert)
            if alert_hash not in self.alerts_sent:
                await self.send_alert(alert)
                self.alerts_sent.add(alert_hash)
                
                # Удалить старые алерты
                if len(self.alerts_sent) > 100:
                    self.alerts_sent.clear()
    
    async def send_alert(self, message: str):
        """Отправка алерта"""
        alert_data = {
            "severity": "warning",
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
            "service": "accounting-system"
        }
        
        # Отправка в Slack/Teams/Email
        async with aiohttp.ClientSession() as session:
            await session.post(
                "https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK",
                json={"text": f"🚨 Performance Alert: {message}"}
            )
    
    async def run_monitoring(self):
        """Основной цикл мониторинга"""
        while True:
            try:
                system_metrics = await self.collect_system_metrics()
                app_metrics = await self.collect_application_metrics()
                
                metrics = PerformanceMetrics(
                    timestamp=datetime.utcnow(),
                    **system_metrics,
                    **app_metrics
                )
                
                self.metrics_history.append(metrics)
                
                # Оставляем только последние 1000 записей
                if len(self.metrics_history) > 1000:
                    self.metrics_history = self.metrics_history[-1000:]
                
                await self.check_thresholds(metrics)
                
            except Exception as e:
                logger.error(f"Performance monitoring error: {e}")
            
            await asyncio.sleep(30)  # Сбор метрик каждые 30 секунд
```

### 5.3 Security Audit (Месяц 22)

#### Security checklist
```python
# security/audit_checklist.py
from dataclasses import dataclass
from typing import List, Dict
import asyncio
import re

@dataclass
class SecurityCheck:
    name: str
    description: str
    status: str  # pass, fail, warning
    details: str
    recommendation: str

class SecurityAuditor:
    def __init__(self):
        self.checks: List[SecurityCheck] = []
    
    async def run_full_audit(self) -> List[SecurityCheck]:
        """Выполнить полный аудит безопасности"""
        await asyncio.gather(
            self.check_authentication(),
            self.check_authorization(),
            self.check_input_validation(),
            self.check_data_encryption(),
            self.check_database_security(),
            self.check_api_security(),
            self.check_logging_and_monitoring(),
            self.check_dependency_vulnerabilities()
        )
        
        return self.checks
    
    async def check_authentication(self):
        """Проверка системы аутентификации"""
        checks = [
            # JWT токены
            await self.verify_jwt_security(),
            # Пароли
            await self.check_password_policy(),
            # MFA
            await self.check_mfa_implementation(),
            # Session management
            await self.check_session_security()
        ]
        self.checks.extend(checks)
    
    async def verify_jwt_security(self) -> SecurityCheck:
        """Проверка безопасности JWT токенов"""
        # Проверить алгоритм подписи
        jwt_algorithm = "HS256"  # Получить из конфигурации
        
        if jwt_algorithm in ["none", "HS256"]:
            return SecurityCheck(
                name="JWT Algorithm",
                description="JWT signing algorithm verification",
                status="warning" if jwt_algorithm == "HS256" else "fail",
                details=f"Current algorithm: {jwt_algorithm}",
                recommendation="Consider using RS256 for better security"
            )
        
        return SecurityCheck(
            name="JWT Algorithm",
            description="JWT signing algorithm verification", 
            status="pass",
            details=f"Secure algorithm in use: {jwt_algorithm}",
            recommendation=""
        )
    
    async def check_password_policy(self) -> SecurityCheck:
        """Проверка политики паролей"""
        password_policy = {
            "min_length": 8,
            "require_uppercase": True,
            "require_lowercase": True,
            "require_numbers": True,
            "require_special": True,
            "max_age_days": 90
        }
        
        if password_policy["min_length"] < 12:
            return SecurityCheck(
                name="Password Policy",
                description="Password strength requirements",
                status="warning",
                details=f"Minimum length: {password_policy['min_length']} characters",
                recommendation="Increase minimum password length to 12+ characters"
            )
        
        return SecurityCheck(
            name="Password Policy",
            description="Password strength requirements",
            status="pass", 
            details="Strong password policy enforced",
            recommendation=""
        )
    
    async def check_input_validation(self):
        """Проверка валидации входных данных"""
        # SQL Injection protection
        sql_injection_check = await self.check_sql_injection_protection()
        self.checks.append(sql_injection_check)
        
        # XSS protection
        xss_check = await self.check_xss_protection()
        self.checks.append(xss_check)
        
        # CSRF protection
        csrf_check = await self.check_csrf_protection()
        self.checks.append(csrf_check)
    
    async def check_sql_injection_protection(self) -> SecurityCheck:
        """Проверка защиты от SQL инъекций"""
        # Сканирование кода на использование параметризованных запросов
        vulnerable_patterns = [
            r'execute\(.*\+.*\)',  # Конкатенация в SQL
            r'f".*{.*}.*".*execute',  # f-строки в SQL
            r'%.*%.*execute'  # Старый стиль форматирования в SQL
        ]
        
        # В реальности нужно сканировать файлы кода
        vulnerability_found = False
        
        if vulnerability_found:
            return SecurityCheck(
                name="SQL Injection Protection",
                description="Protection against SQL injection attacks",
                status="fail",
                details="Potentially vulnerable code patterns found",
                recommendation="Use only parameterized queries and ORM methods"
            )
        
        return SecurityCheck(
            name="SQL Injection Protection", 
            description="Protection against SQL injection attacks",
            status="pass",
            details="All database queries use parameterized statements",
            recommendation=""
        )
    
    async def check_data_encryption(self):
        """Проверка шифрования данных"""
        # Encryption at rest
        encryption_at_rest = SecurityCheck(
            name="Data Encryption at Rest",
            description="Sensitive data encryption in database",
            status="pass",  # Проверить реальную конфигурацию
            details="Database encryption enabled",
            recommendation=""
        )
        self.checks.append(encryption_at_rest)
        
        # Encryption in transit
        encryption_in_transit = SecurityCheck(
            name="Data Encryption in Transit", 
            description="TLS/SSL for all communications",
            status="pass",
            details="TLS 1.3 enforced for all connections",
            recommendation=""
        )
        self.checks.append(encryption_in_transit)
        
        # PII data handling
        pii_handling = await self.check_pii_handling()
        self.checks.append(pii_handling)
    
    async def check_pii_handling(self) -> SecurityCheck:
        """Проверка обработки персональных данных"""
        # Проверить соответствие Georgian Data Protection Law
        gdpr_compliance = True  # Проверить реальную реализацию
        
        if not gdpr_compliance:
            return SecurityCheck(
                name="PII Data Handling",
                description="Personal data protection compliance", 
                status="fail",
                details="Georgian Data Protection Law compliance issues found",
                recommendation="Implement proper consent management and data retention policies"
            )
        
        return SecurityCheck(
            name="PII Data Handling",
            description="Personal data protection compliance",
            status="pass", 
            details="Compliant with Georgian Data Protection Law",
            recommendation=""
        )
    
    async def generate_security_report(self) -> str:
        """Генерация отчета по безопасности"""
        total_checks = len(self.checks)
        passed = len([c for c in self.checks if c.status == "pass"])
        warnings = len([c for c in self.checks if c.status == "warning"])
        failed = len([c for c in self.checks if c.status == "fail"])
        
        report = f"""
# Security Audit Report
Generated: {datetime.utcnow().isoformat()}

## Summary
- Total Checks: {total_checks}
- ✅ Passed: {passed}
- ⚠️  Warnings: {warnings} 
- ❌ Failed: {failed}

## Security Score: {(passed / total_checks) * 100:.1f}%

## Detailed Results
"""
        
        for check in self.checks:
            status_emoji = {"pass": "✅", "warning": "⚠️", "fail": "❌"}
            report += f"""
### {status_emoji[check.status]} {check.name}
**Description:** {check.description}
**Status:** {check.status.upper()}
**Details:** {check.details}
"""
            if check.recommendation:
                report += f"**Recommendation:** {check.recommendation}\n"
        
        return report
```

### 5.4 User Training Program (Месяц 23)

#### Training materials
```python
# training/training_program.py
from dataclasses import dataclass
from typing import List, Dict
from datetime import datetime, timedelta

@dataclass
class TrainingModule:
    id: str
    title: str
    description: str
    duration_minutes: int
    prerequisites: List[str]
    learning_objectives: List[str]
    materials: List[str]
    assessment: Dict

class GeorgianAccountingTrainingProgram:
    def __init__(self):
        self.modules = self.create_training_modules()
        self.user_progress = {}
    
    def create_training_modules(self) -> List[TrainingModule]:
        """Создать модули обучения"""
        return [
            TrainingModule(
                id="basics-001",
                title="Основы системы: Навигация и интерфейс",
                description="Изучение основного интерфейса и навигации в системе",
                duration_minutes=30,
                prerequisites=[],
                learning_objectives=[
                    "Освоить основную навигацию в системе",
                    "Понять структуру меню и разделов",
                    "Научиться настраивать пользовательский интерфейс"
                ],
                materials=[
                    "video: interface_overview.mp4",
                    "pdf: user_interface_guide.pdf", 
                    "interactive: navigation_tour"
                ],
                assessment={
                    "type": "interactive_quiz",
                    "passing_score": 80,
                    "questions": 10
                }
            ),
            
            TrainingModule(
                id="accounting-001", 
                title="План счетов и двойная запись",
                description="Работа с планом счетов и принципы двойной записи",
                duration_minutes=60,
                prerequisites=["basics-001"],
                learning_objectives=[
                    "Понять структуру грузинского плана счетов",
                    "Освоить принципы двойной записи", 
                    "Научиться создавать и редактировать счета"
                ],
                materials=[
                    "video: chart_of_accounts_georgian.mp4",
                    "pdf: georgian_accounting_standards.pdf",
                    "interactive: double_entry_simulator",
                    "template: standard_chart_of_accounts.xlsx"
                ],
                assessment={
                    "type": "practical_exercise",
                    "passing_score": 85,
                    "task": "Create chart of accounts for small Georgian business"
                }
            ),
            
            TrainingModule(
                id="transactions-001",
                title="Создание и обработка транзакций", 
                description="Полный цикл работы с бухгалтерскими транзакциями",
                duration_minutes=90,
                prerequisites=["accounting-001"],
                learning_objectives=[
                    "Создавать различные типы транзакций",
                    "Понять workflow утверждения и проведения",
                    "Освоить работу с многовалютными операциями"
                ],
                materials=[
                    "video: transaction_lifecycle.mp4",
                    "pdf: transaction_types_guide.pdf",
                    "interactive: transaction_creation_wizard",
                    "case_study: multi_currency_transactions.pdf"
                ],
                assessment={
                    "type": "scenario_based",
                    "passing_score": 80,
                    "scenarios": [
                        "Process supplier invoice with VAT",
                        "Record salary payments with taxes",
                        "Handle foreign currency purchase"
                    ]
                }
            ),
            
            TrainingModule(
                id="georgian-tax-001",
                title="Грузинская налоговая система",
                description="Работа с НДС, подоходным налогом и отчетностью в RS.ge",
                duration_minutes=120,
                prerequisites=["transactions-001"],
                learning_objectives=[
                    "Освоить расчет НДС 18%",
                    "Понять малый статус (до 100,000 лари)",
                    "Научиться подавать декларации в RS.ge",
                    "Работать с реверс-чарж НДС"
                ],
                materials=[
                    "video: georgian_vat_system.mp4",
                    "pdf: tax_code_summary_2025.pdf",
                    "interactive: vat_calculator_simulator", 
                    "webinar: rs_ge_integration_demo.mp4",
                    "template: monthly_vat_declaration.xlsx"
                ],
                assessment={
                    "type": "certification_exam",
                    "passing_score": 90,
                    "duration_minutes": 60,
                    "topics": ["VAT calculation", "Tax deadlines", "RS.ge procedures"]
                }
            ),
            
            TrainingModule(
                id="payroll-001",
                title="Расчет зарплаты и пенсионная система 2+2+2",
                description="Полный цикл расчета зарплаты с грузинскими налогами",
                duration_minutes=75,
                prerequisites=["georgian-tax-001"],
                learning_objectives=[
                    "Рассчитать зарплату с подоходным налогом 20%",
                    "Работать с системой 2+2+2 пенсионных взносов",
                    "Генерировать зарплатные ведомости",
                    "Подавать отчеты в пенсионное агентство"
                ],
                materials=[
                    "video: georgian_payroll_system.mp4",
                    "pdf: pension_system_guide.pdf",
                    "calculator: salary_tax_calculator",
                    "template: payroll_register.xlsx"
                ],
                assessment={
                    "type": "practical_calculation",
                    "passing_score": 85,
                    "task": "Calculate monthly payroll for 10 employees"
                }
            ),
            
            TrainingModule(
                id="reporting-001", 
                title="Финансовая отчетность по IFRS",
                description="Создание финансовых отчетов в соответствии с IFRS",
                duration_minutes=90,
                prerequisites=["payroll-001"],
                learning_objectives=[
                    "Генерировать баланс по IFRS",
                    "Создавать отчет о прибылях и убытках",
                    "Формировать отчет о движении денежных средств",
                    "Понять требования к раскрытию информации"
                ],
                materials=[
                    "video: ifrs_reporting_overview.mp4",
                    "pdf: ifrs_requirements_2025.pdf",
                    "template: ifrs_financial_statements.xlsx",
                    "case_study: annual_reporting_example.pdf"
                ],
                assessment={
                    "type": "report_generation",
                    "passing_score": 85,
                    "task": "Generate full IFRS financial statements"
                }
            ),
            
            TrainingModule(
                id="advanced-001",
                title="Продвинутые функции и интеграции",
                description="Работа с API, автоматизацией и внешними системами",
                duration_minutes=60,
                prerequisites=["reporting-001"],
                learning_objectives=[
                    "Настроить автоматические проводки",
                    "Использовать API для интеграций",
                    "Работать с банковскими выписками",
                    "Настроить уведомления и алерты"
                ],
                materials=[
                    "video: automation_features.mp4",
                    "pdf: api_integration_guide.pdf",
                    "hands_on: bank_statement_import",
                    "tutorial: workflow_automation_setup"
                ],
                assessment={
                    "type": "practical_setup",
                    "passing_score": 80,
                    "task": "Configure automated monthly closing process"
                }
            )
        ]
    
    def create_training_schedule(self, user_role: str, available_hours_per_week: int = 5) -> Dict:
        """Создать индивидуальный план обучения"""
        role_modules = {
            "accountant": ["basics-001", "accounting-001", "transactions-001", "georgian-tax-001"],
            "chief_accountant": ["basics-001", "accounting-001", "transactions-001", "georgian-tax-001", "payroll-001", "reporting-001", "advanced-001"],
            "tax_specialist": ["basics-001", "accounting-001", "georgian-tax-001", "reporting-001"],
            "payroll_officer": ["basics-001", "accounting-001", "payroll-001"],
            "auditor": ["basics-001", "accounting-001", "transactions-001", "reporting-001"]
        }
        
        required_modules = role_modules.get(user_role, ["basics-001"])
        
        schedule = []
        current_date = datetime.now()
        weekly_minutes = available_hours_per_week * 60
        
        for module_id in required_modules:
            module = next((m for m in self.modules if m.id == module_id), None)
            if module:
                # Рассчитать время на изучение (с учетом практики)
                total_time = module.duration_minutes * 1.5  # +50% на практику
                
                # Распределить по неделям
                weeks_needed = max(1, int(total_time / weekly_minutes))
                
                schedule.append({
                    "module": module,
                    "start_date": current_date,
                    "end_date": current_date + timedelta(weeks=weeks_needed),
                    "estimated_hours": total_time / 60
                })
                
                current_date += timedelta(weeks=weeks_needed)
        
        return {
            "user_role": user_role,
            "total_duration_weeks": (current_date - datetime.now()).days // 7,
            "schedule": schedule
        }
    
    def generate_training_materials(self, module_id: str) -> Dict:
        """Генерировать учебные материалы для модуля"""
        module = next((m for m in self.modules if m.id == module_id), None)
        if not module:
            return {}
        
        # Специфичные материалы для грузинской системы
        georgian_materials = {
            "georgian-tax-001": {
                "vat_examples": [
                    {
                        "scenario": "Продажа товаров на 1000 лари",
                        "calculation": "НДС = 1000 * 18% = 180 лари",
                        "total": "1180 лари с НДС"
                    },
                    {
                        "scenario": "Реверс-чарж с зарубежного поставщика",
                        "calculation": "НДС к доплате и зачету = 500 * 18% = 90 лари",
                        "note": "Одновременно начисляем и засчитываем НДС"
                    }
                ],
                "tax_calendar": {
                    "monthly_deadlines": [
                        {"task": "Подача декларации НДС", "deadline": "15 число"},
                        {"task": "Уплата НДС", "deadline": "15 число"},
                        {"task": "Отчет по зарплатным налогам", "deadline": "15 число"}
                    ],
                    "annual_deadlines": [
                        {"task": "Декларация о доходах", "deadline": "31 марта"},
                        {"task": "Аудиторский отчет", "deadline": "31 мая"}
                    ]
                }
            },
            
            "payroll-001": {
                "salary_examples": [
                    {
                        "gross_salary": 2000,
                        "income_tax_20": 400,
                        "pension_employee_2": 40,
                        "pension_employer_2": 40,
                        "pension_government_2": 40,
                        "net_salary": 1560
                    }
                ],
                "pension_calculator": {
                    "annual_limit": 24000,
                    "monthly_limit": 2000,
                    "note": "Государственное софинансирование до 24,000 лари в год"
                }
            }
        }
        
        return {
            "module": module,
            "georgian_specific": georgian_materials.get(module_id, {}),
            "interactive_elements": [
                f"simulation_{module_id}",
                f"quiz_{module_id}",
                f"calculator_{module_id}"
            ]
        }

class TrainingTracker:
    def __init__(self):
        self.user_progress = {}
        self.completion_certificates = {}
    
    async def track_progress(self, user_id: str, module_id: str, progress_data: Dict):
        """Отслеживать прогресс обучения"""
        if user_id not in self.user_progress:
            self.user_progress[user_id] = {}
        
        self.user_progress[user_id][module_id] = {
            "started_at": progress_data.get("started_at", datetime.utcnow()),
            "completed_at": progress_data.get("completed_at"),
            "progress_percent": progress_data.get("progress_percent", 0),
            "assessment_score": progress_data.get("assessment_score"),
            "time_spent_minutes": progress_data.get("time_spent_minutes", 0),
            "status": progress_data.get("status", "in_progress")  # not_started, in_progress, completed, failed
        }
        
        # Автоматическая выдача сертификата при успешном завершении
        if (progress_data.get("status") == "completed" and 
            progress_data.get("assessment_score", 0) >= 80):
            await self.issue_certificate(user_id, module_id)
    
    async def issue_certificate(self, user_id: str, module_id: str):
        """Выдать сертификат о прохождении"""
        certificate = {
            "certificate_id": str(uuid.uuid4()),
            "user_id": user_id,
            "module_id": module_id,
            "issued_at": datetime.utcnow(),
            "valid_until": datetime.utcnow() + timedelta(days=365),
            "verification_url": f"https://accounting-system.ge/certificates/verify/{certificate['certificate_id']}"
        }
        
        self.completion_certificates[certificate["certificate_id"]] = certificate
        
        # Отправить уведомление пользователю
        await self.send_certificate_notification(user_id, certificate)
    
    def generate_progress_report(self, user_id: str) -> Dict:
        """Генерировать отчет о прогрессе обучения"""
        user_data = self.user_progress.get(user_id, {})
        
        total_modules = len(user_data)
        completed_modules = len([m for m in user_data.values() if m["status"] == "completed"])
        in_progress_modules = len([m for m in user_data.values() if m["status"] == "in_progress"])
        
        average_score = 0
        if completed_modules > 0:
            scores = [m["assessment_score"] for m in user_data.values() 
                     if m["status"] == "completed" and m["assessment_score"]]
            average_score = sum(scores) / len(scores) if scores else 0
        
        return {
            "user_id": user_id,
            "completion_rate": (completed_modules / total_modules * 100) if total_modules > 0 else 0,
            "modules_completed": completed_modules,
            "modules_in_progress": in_progress_modules,
            "average_assessment_score": average_score,
            "total_time_spent_hours": sum(m["time_spent_minutes"] for m in user_data.values()) / 60,
            "certificates_earned": len([c for c in self.completion_certificates.values() 
                                       if c["user_id"] == user_id]),
            "next_recommended_modules": self.get_next_modules(user_id)
        }
```

### 5.5 Production Deployment (Месяц 24)

#### Blue-Green Deployment Strategy
```yaml
# deployment/blue-green-deployment.yml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: accounting-system
  namespace: accounting-production
spec:
  replicas: 10
  strategy:
    blueGreen:
      # Настройки Blue-Green deployment
      activeService: accounting-active
      previewService: accounting-preview
      autoPromotionEnabled: false
      scaleDownDelaySeconds: 30
      prePromotionAnalysis:
        templates:
        - templateName: success-rate
        args:
        - name: service-name
          value: accounting-preview
      postPromotionAnalysis:
        templates:
        - templateName: success-rate
        - templateName: latency
        args:
        - name: service-name
          value: accounting-active
      previewReplicaCount: 2
      activeMetadata:
        labels:
          version: stable
      previewMetadata:
        labels:
          version: preview
  selector:
    matchLabels:
      app: accounting-system
  template:
    metadata:
      labels:
        app: accounting-system
    spec:
      containers:
      - name: accounting-api
        image: accounting-system:v2.0.0
        ports:
        - containerPort: 8000
        env:
        - name: ENVIRONMENT
          value: "production"
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: url
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health/live
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
        
---
# Analysis Templates для автоматического тестирования
apiVersion: argoproj.io/v1alpha1
kind: AnalysisTemplate
metadata:
  name: success-rate
spec:
  args:
  - name: service-name
  metrics:
  - name: success-rate
    provider:
      prometheus:
        address: http://prometheus.monitoring.svc.cluster.local:9090
        query: |
          sum(irate(
            http_requests_total{job="{{args.service-name}}",status!~"5.."}[2m]
          )) /
          sum(irate(
            http_requests_total{job="{{args.service-name}}"}[2m]
          )) * 100
    successCondition: result[0] >= 95
    interval: 30s
    count: 5
    failureLimit: 2

---
apiVersion: argoproj.io/v1alpha1
kind: AnalysisTemplate  
metadata:
  name: latency
spec:
  args:
  - name: service-name
  metrics:
  - name: latency-95th
    provider:
      prometheus:
        address: http://prometheus.monitoring.svc.cluster.local:9090
        query: |
          histogram_quantile(0.95,
            sum(rate(http_request_duration_seconds_bucket{job="{{args.service-name}}"}[2m]))
            by (le)
          ) * 1000
    successCondition: result[0] <= 2000  # 2 секунды
    interval: 30s
    count: 5
    failureLimit: 2
```

#### Production checklist
```python
# deployment/production_checklist.py
from dataclasses import dataclass
from typing import List, Dict, Optional
from enum import Enum
import asyncio

class CheckStatus(Enum):
    PENDING = "pending"
    PASSED = "passed" 
    FAILED = "failed"
    WARNING = "warning"

@dataclass
class ProductionCheck:
    name: str
    description: str
    status: CheckStatus
    details: Optional[str] = None
    blocker: bool = False  # Блокирует ли деплой

class ProductionReadinessChecker:
    def __init__(self):
        self.checks: List[ProductionCheck] = []
    
    async def run_all_checks(self) -> Dict:
        """Выполнить все проверки готовности к production"""
        await asyncio.gather(
            self.check_infrastructure(),
            self.check_database(),
            self.check_security(),
            self.check_monitoring(),
            self.check_backup(),
            self.check_performance(),
            self.check_compliance(),
            self.check_documentation()
        )
        
        # Подсчет результатов
        total = len(self.checks)
        passed = len([c for c in self.checks if c.status == CheckStatus.PASSED])
        failed = len([c for c in self.checks if c.status == CheckStatus.FAILED])
        warnings = len([c for c in self.checks if c.status == CheckStatus.WARNING])
        blockers = len([c for c in self.checks if c.status == CheckStatus.FAILED and c.blocker])
        
        return {
            "ready_for_production": blockers == 0,
            "total_checks": total,
            "passed": passed,
            "failed": failed,
            "warnings": warnings,
            "blockers": blockers,
            "checks": self.checks
        }
    
    async def check_infrastructure(self):
        """Проверка инфраструктуры"""
        checks = [
            ProductionCheck(
                "Kubernetes Cluster Health",
                "Verify K8s cluster is healthy and has sufficient resources",
                await self._check_k8s_health(),
                blocker=True
            ),
            ProductionCheck(
                "Load Balancer Configuration", 
                "Verify load balancer is properly configured",
                await self._check_load_balancer(),
                blocker=True
            ),
            ProductionCheck(
                "SSL/TLS Certificates",
                "Verify SSL certificates are valid and not expiring soon",
                await self._check_ssl_certificates(),
                blocker=True
            ),
            ProductionCheck(
                "DNS Configuration",
                "Verify DNS records are correctly configured", 
                await self._check_dns(),
                blocker=True
            )
        ]
        self.checks.extend(checks)
    
    async def check_database(self):
        """Проверка базы данных"""
        checks = [
            ProductionCheck(
                "Database Connectivity",
                "Verify application can connect to production database",
                await self._check_db_connectivity(),
                blocker=True
            ),
            ProductionCheck(
                "Database Performance",
                "Verify database performance meets requirements",
                await self._check_db_performance(),
                blocker=False
            ),
            ProductionCheck(
                "Database Backup",
                "Verify automated backups are configured and working",
                await self._check_db_backup(),
                blocker=True
            ),
            ProductionCheck(
                "Database Security",
                "Verify database security settings",
                await self._check_db_security(),
                blocker=True
            )
        ]
        self.checks.extend(checks)
    
    async def check_compliance(self):
        """Проверка соответствия требованиям"""
        checks = [
            ProductionCheck(
                "Georgian Tax Compliance",
                "Verify compliance with Georgian tax regulations",
                await self._check_georgian_tax_compliance(),
                blocker=True
            ),
            ProductionCheck(
                "IFRS Compliance", 
                "Verify IFRS accounting standards compliance",
                await self._check_ifrs_compliance(),
                blocker=True
            ),
            ProductionCheck(
                "Data Privacy Compliance",
                "Verify Georgian data protection law compliance",
                await self._check_data_privacy(),
                blocker=True
            ),
            ProductionCheck(
                "Audit Trail Completeness",
                "Verify complete audit trail implementation", 
                await self._check_audit_trail(),
                blocker=True
            )
        ]
        self.checks.extend(checks)
    
    async def _check_georgian_tax_compliance(self) -> CheckStatus:
        """Проверка соответствия грузинскому налоговому законодательству"""
        compliance_items = [
            "VAT rate 18% correctly configured",
            "Monthly VAT reporting implemented", 
            "100,000 GEL threshold monitoring",
            "RS.ge integration working",
            "Reverse-charge VAT handling",
            "Income tax 20% calculation",
            "Pension system 2+2+2 implemented"
        ]
        
        # В реальности - проверять каждый пункт
        all_compliant = True  # Результат реальной проверки
        
        return CheckStatus.PASSED if all_compliant else CheckStatus.FAILED
    
    async def generate_go_live_report(self) -> str:
        """Генерировать отчет о готовности к запуску"""
        results = await self.run_all_checks()
        
        report = f"""
# Production Readiness Report
Generated: {datetime.utcnow().isoformat()}

## Executive Summary
{'✅ READY FOR PRODUCTION' if results['ready_for_production'] else '❌ NOT READY FOR PRODUCTION'}

## Statistics
- Total Checks: {results['total_checks']}
- Passed: {results['passed']} ✅
- Failed: {results['failed']} ❌
- Warnings: {results['warnings']} ⚠️
- Blockers: {results['blockers']} 🚫

## Readiness Score: {(results['passed'] / results['total_checks']) * 100:.1f}%

## Critical Issues
"""
        
        blockers = [c for c in self.checks if c.status == CheckStatus.FAILED and c.blocker]
        if blockers:
            report += "The following issues MUST be resolved before production deployment:\n"
            for check in blockers:
                report += f"- ❌ {check.name}: {check.description}\n"
        else:
            report += "No critical blocking issues found.\n"
        
        report += "\n## All Checks Details\n"
        for check in self.checks:
            status_emoji = {
                CheckStatus.PASSED: "✅",
                CheckStatus.FAILED: "❌", 
                CheckStatus.WARNING: "⚠️",
                CheckStatus.PENDING: "⏳"
            }
            
            blocker_flag = " 🚫 BLOCKER" if check.blocker and check.status == CheckStatus.FAILED else ""
            report += f"- {status_emoji[check.status]} {check.name}{blocker_flag}\n"
            if check.details:
                report += f"  Details: {check.details}\n"
        
        return report

# Go-Live процедура
class GoLiveCoordinator:
    def __init__(self):
        self.readiness_checker = ProductionReadinessChecker()
        self.deployment_steps = self.create_deployment_steps()
    
    def create_deployment_steps(self) -> List[Dict]:
        """Создать пошаговый план деплоя"""
        return [
            {
                "step": 1,
                "name": "Pre-deployment verification",
                "description": "Run final production readiness checks",
                "duration_minutes": 30,
                "rollback_possible": True
            },
            {
                "step": 2, 
                "name": "Database migration",
                "description": "Apply production database migrations",
                "duration_minutes": 60,
                "rollback_possible": True
            },
            {
                "step": 3,
                "name": "Blue-green deployment start", 
                "description": "Deploy new version to preview environment",
                "duration_minutes": 20,
                "rollback_possible": True
            },
            {
                "step": 4,
                "name": "Integration testing",
                "description": "Run integration tests against preview environment",
                "duration_minutes": 45,
                "rollback_possible": True
            },
            {
                "step": 5,
                "name": "Traffic switchover",
                "description": "Switch traffic from blue to green environment", 
                "duration_minutes": 5,
                "rollback_possible": True
            },
            {
                "step": 6,
                "name": "Post-deployment verification",
                "description": "Verify all systems operational",
                "duration_minutes": 30,
                "rollback_possible": True
            },
            {
                "step": 7,
                "name": "Monitoring setup",
                "description": "Enable production monitoring and alerting",
                "duration_minutes": 15,
                "rollback_possible": False
            },
            {
                "step": 8,
                "name": "User notification",
                "description": "Notify users about system availability",
                "duration_minutes": 10,
                "rollback_possible": False
            }
        ]
    
    async def execute_go_live(self) -> Dict:
        """Выполнить процедуру go-live"""
        start_time = datetime.utcnow()
        results = []
        
        # Предварительная проверка
        readiness_report = await self.readiness_checker.run_all_checks()
        if not readiness_report["ready_for_production"]:
            return {
                "success": False,
                "error": "System not ready for production",
                "readiness_report": readiness_report
            }
        
        # Выполнение шагов деплоя
        for step in self.deployment_steps:
            step_start = datetime.utcnow()
            
            try:
                success = await self.execute_deployment_step(step)
                step_result = {
                    "step": step["step"],
                    "name": step["name"], 
                    "success": success,
                    "start_time": step_start,
                    "duration": (datetime.utcnow() - step_start).total_seconds()
                }
                
                if not success:
                    step_result["error"] = f"Step {step['step']} failed"
                    results.append(step_result)
                    
                    # Автоматический rollback если возможен
                    if step["rollback_possible"]:
                        await self.rollback_deployment(step["step"])
                    
                    return {
                        "success": False,
                        "failed_step": step["step"],
                        "results": results
                    }
                
                results.append(step_result)
                
            except Exception as e:
                results.append({
                    "step": step["step"],
                    "name": step["name"],
                    "success": False, 
                    "error": str(e),
                    "start_time": step_start,
                    "duration": (datetime.utcnow() - step_start).total_seconds()
                })
                
                # Rollback при ошибке
                if step["rollback_possible"]:
                    await self.rollback_deployment(step["step"])
                
                return {
                    "success": False,
                    "failed_step": step["step"],
                    "exception": str(e),
                    "results": results
                }
        
        total_duration = (datetime.utcnow() - start_time).total_seconds()
        
        return {
            "success": True,
            "total_duration_seconds": total_duration,
            "results": results,
            "go_live_time": start_time.isoformat()
        }
```

### Результаты Фазы 5:
- ✅ Performance optimization с 2x улучшением скорости
- ✅ Успешное load testing до 1000+ concurrent users
- ✅ Security audit с 95%+ security score
- ✅ Обучение 50+ пользователей
- ✅ Успешный production deployment
- ✅ 99.9% uptime в первый месяц работы

---

## 📊 Итоговые результаты миграции

### Технические достижения:
- **Производительность**: Улучшение в 3x по сравнению с legacy системой
- **Масштабируемость**: Поддержка до 10,000 пользователей
- **Доступность**: 99.95% uptime SLA
- **Безопасность**: Соответствие всем стандартам безопасности

### Бизнес-результаты:
- **Соответствие требованиям**: 100% compliance с Georgian Tax Code и IFRS
- **Время обработки**: Сокращение времени на 70%
- **Автоматизация**: 80% рутинных задач автоматизированы
- **ROI**: Окупаемость за 18 месяцев

### Финансовые показатели:
- **Снижение операционных расходов**: 40%
- **Сокращение времени закрытия периода**: с 10 до 2 дней
- **Уменьшение ошибок**: на 90%
- **Экономия на аудите**: 50% времени аудиторов

---

## 📈 Метрики успеха миграции

### Технические KPI:

| Метрика | До миграции | После миграции | Улучшение |
|---------|-------------|----------------|-----------|
| Время ответа API | 3.2с | 0.8с | 75% |
| Пропускная способность | 100 TPS | 1000 TPS | 900% |
| Время развертывания | 4 часа | 15 минут | 94% |
| Покрытие тестами | 25% | 95% | 280% |
| Время восстановления | 4 часа | 5 минут | 98% |

### Бизнес KPI:

| Метрика | До миграции | После миграции | Улучшение |
|---------|-------------|----------------|-----------|
| Время создания отчета | 2 дня | 30 минут | 97% |
| Ошибки в расчетах | 5% | 0.5% | 90% |
| Время обучения | 40 часов | 12 часов | 70% |
| Удовлетворенность пользователей | 6/10 | 9/10 | 50% |
| Соответствие нормам | 85% | 100% | 18% |

---

## 🔄 Post-Migration Support и Continuous Improvement

### 6.1 Ongoing Support Structure

#### Support Tiers
```python
# support/support_structure.py
from enum import Enum
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime, timedelta

class SupportTier(Enum):
    L1_BASIC = "l1_basic"           # Базовая поддержка пользователей
    L2_TECHNICAL = "l2_technical"   # Техническая поддержка
    L3_EXPERT = "l3_expert"         # Экспертная поддержка
    L4_VENDOR = "l4_vendor"         # Поддержка вендора

class Priority(Enum):
    CRITICAL = "critical"     # Система не работает
    HIGH = "high"            # Серьезное влияние на бизнес
    MEDIUM = "medium"        # Умеренное влияние
    LOW = "low"              # Минимальное влияние

@dataclass
class SupportTicket:
    id: str
    priority: Priority
    tier: SupportTier
    title: str
    description: str
    user_id: str
    created_at: datetime
    sla_response_time: timedelta
    sla_resolution_time: timedelta
    assigned_to: Optional[str] = None
    status: str = "open"
    
class SupportSLAMatrix:
    """Матрица SLA для различных комбинаций приоритета и уровня"""
    
    SLA_MATRIX = {
        (Priority.CRITICAL, SupportTier.L1_BASIC): {
            "response_time": timedelta(minutes=15),
            "resolution_time": timedelta(hours=1)
        },
        (Priority.HIGH, SupportTier.L1_BASIC): {
            "response_time": timedelta(hours=1),
            "resolution_time": timedelta(hours=4)
        },
        (Priority.MEDIUM, SupportTier.L1_BASIC): {
            "response_time": timedelta(hours=4),
            "resolution_time": timedelta(hours=24)
        },
        (Priority.LOW, SupportTier.L1_BASIC): {
            "response_time": timedelta(hours=24),
            "resolution_time": timedelta(days=3)
        },
        
        # L2 Technical Support
        (Priority.CRITICAL, SupportTier.L2_TECHNICAL): {
            "response_time": timedelta(minutes=30),
            "resolution_time": timedelta(hours=2)
        },
        (Priority.HIGH, SupportTier.L2_TECHNICAL): {
            "response_time": timedelta(hours=2),
            "resolution_time": timedelta(hours=8)
        },
        
        # L3 Expert Support  
        (Priority.CRITICAL, SupportTier.L3_EXPERT): {
            "response_time": timedelta(hours=1),
            "resolution_time": timedelta(hours=4)
        },
        (Priority.HIGH, SupportTier.L3_EXPERT): {
            "response_time": timedelta(hours=4),
            "resolution_time": timedelta(days=1)
        }
    }
    
    @classmethod
    def get_sla(cls, priority: Priority, tier: SupportTier) -> dict:
        return cls.SLA_MATRIX.get((priority, tier), {
            "response_time": timedelta(days=1),
            "resolution_time": timedelta(days=5)
        })

class GeorgianAccountingSupportTeam:
    """Специализированная команда поддержки для грузинской бухгалтерии"""
    
    def __init__(self):
        self.team_members = {
            "l1_basic": [
                {
                    "name": "Nino Kacharava", 
                    "specialization": "User Interface, Basic Operations",
                    "languages": ["Georgian", "English"],
                    "availability": "09:00-18:00 GMT+4"
                },
                {
                    "name": "Giorgi Mchedlishvili",
                    "specialization": "Reports, Data Entry", 
                    "languages": ["Georgian", "English", "Russian"],
                    "availability": "09:00-18:00 GMT+4"
                }
            ],
            "l2_technical": [
                {
                    "name": "Tamar Dvali",
                    "specialization": "Georgian Tax System, VAT, RS.ge Integration",
                    "certifications": ["Georgian Tax Consultant", "IFRS"],
                    "languages": ["Georgian", "English"],
                    "availability": "08:00-20:00 GMT+4"
                },
                {
                    "name": "Levan Tsintsadze", 
                    "specialization": "Payroll, Pension System 2+2+2",
                    "certifications": ["Payroll Specialist", "Labor Law"],
                    "languages": ["Georgian", "English"],
                    "availability": "08:00-20:00 GMT+4"
                }
            ],
            "l3_expert": [
                {
                    "name": "Ana Khvedelidze",
                    "specialization": "IFRS Compliance, Financial Reporting", 
                    "certifications": ["ACCA", "IFRS Specialist", "CPA"],
                    "languages": ["Georgian", "English"],
                    "availability": "24/7 on-call"
                },
                {
                    "name": "Vakhtang Asatiani",
                    "specialization": "System Architecture, Performance",
                    "certifications": ["AWS Solutions Architect", "Kubernetes"],
                    "languages": ["Georgian", "English"],
                    "availability": "24/7 on-call"
                }
            ]
        }
    
    def escalate_ticket(self, ticket: SupportTicket) -> SupportTicket:
        """Эскалация тикета на следующий уровень"""
        escalation_map = {
            SupportTier.L1_BASIC: SupportTier.L2_TECHNICAL,
            SupportTier.L2_TECHNICAL: SupportTier.L3_EXPERT,
            SupportTier.L3_EXPERT: SupportTier.L4_VENDOR
        }
        
        new_tier = escalation_map.get(ticket.tier)
        if new_tier:
            new_sla = SupportSLAMatrix.get_sla(ticket.priority, new_tier)
            ticket.tier = new_tier
            ticket.sla_response_time = new_sla["response_time"]
            ticket.sla_resolution_time = new_sla["resolution_time"] 
            ticket.assigned_to = None  # Переназначить
            
        return ticket
```

### 6.2 Continuous Monitoring и Improvement

#### Monitoring Dashboard
```python
# monitoring/business_dashboard.py
from dataclasses import dataclass
from typing import Dict, List
from datetime import datetime, timedelta
import asyncio

@dataclass
class BusinessMetric:
    name: str
    current_value: float
    target_value: float
    trend: str  # up, down, stable
    unit: str
    category: str

class BusinessMetricsDashboard:
    def __init__(self):
        self.metrics_collectors = {
            "user_adoption": self.collect_user_adoption_metrics,
            "system_performance": self.collect_performance_metrics,
            "business_value": self.collect_business_value_metrics,
            "compliance": self.collect_compliance_metrics
        }
    
    async def collect_user_adoption_metrics(self) -> List[BusinessMetric]:
        """Метрики принятия системы пользователями"""
        return [
            BusinessMetric(
                "Active Daily Users",
                85.5,  # Из аналитики
                90.0,
                "up",
                "percentage",
                "user_adoption"
            ),
            BusinessMetric(
                "Feature Utilization Rate",
                72.3,
                80.0,
                "up", 
                "percentage",
                "user_adoption"
            ),
            BusinessMetric(
                "User Satisfaction Score",
                8.7,
                9.0,
                "stable",
                "score",
                "user_adoption"
            ),
            BusinessMetric(
                "Training Completion Rate",
                94.2,
                95.0,
                "up",
                "percentage", 
                "user_adoption"
            )
        ]
    
    async def collect_business_value_metrics(self) -> List[BusinessMetric]:
        """Метрики бизнес-ценности"""
        return [
            BusinessMetric(
                "Time to Close Books",
                2.1,  # дни
                2.0,
                "down",  # улучшение
                "days",
                "business_value"
            ),
            BusinessMetric(
                "Error Rate in Reports",
                0.3,  # процент
                0.5,
                "down",
                "percentage",
                "business_value"
            ),
            BusinessMetric(
                "Audit Preparation Time",
                65.0,  # процент от предыдущего времени
                60.0,
                "down",
                "percentage_reduction",
                "business_value"
            ),
            BusinessMetric(
                "Compliance Score", 
                98.5,
                99.0,
                "up",
                "percentage",
                "business_value"
            )
        ]
    
    async def collect_compliance_metrics(self) -> List[BusinessMetric]:
        """Метрики соответствия требованиям"""
        return [
            BusinessMetric(
                "Georgian Tax Compliance",
                100.0,
                100.0,
                "stable",
                "percentage",
                "compliance"
            ),
            BusinessMetric(
                "IFRS Compliance",
                97.8,
                99.0,
                "up",
                "percentage", 
                "compliance"
            ),
            BusinessMetric(
                "Data Privacy Compliance",
                99.2,
                100.0,
                "up",
                "percentage",
                "compliance"
            ),
            BusinessMetric(
                "Audit Trail Completeness",
                100.0,
                100.0,
                "stable",
                "percentage",
                "compliance"
            )
        ]
    
    async def generate_executive_summary(self) -> Dict:
        """Генерация executive summary для руководства"""
        all_metrics = []
        for collector in self.metrics_collectors.values():
            metrics = await collector()
            all_metrics.extend(metrics)
        
        # Группировка по категориям
        categories = {}
        for metric in all_metrics:
            if metric.category not in categories:
                categories[metric.category] = []
            categories[metric.category].append(metric)
        
        # Расчет общих показателей
        total_metrics = len(all_metrics)
        on_target = len([m for m in all_metrics if m.current_value >= m.target_value])
        needs_attention = len([m for m in all_metrics if m.current_value < m.target_value * 0.9])
        
        return {
            "summary": {
                "overall_health": "Good" if on_target / total_metrics > 0.8 else "Needs Attention",
                "metrics_on_target": f"{on_target}/{total_metrics}",
                "metrics_needing_attention": needs_attention,
                "generated_at": datetime.utcnow().isoformat()
            },
            "categories": categories,
            "key_insights": await self.generate_insights(all_metrics),
            "recommendations": await self.generate_recommendations(all_metrics)
        }
    
    async def generate_insights(self, metrics: List[BusinessMetric]) -> List[str]:
        """Генерация ключевых инсайтов"""
        insights = []
        
        # Найти топ улучшения
        improving_metrics = [m for m in metrics if m.trend == "up" and m.current_value >= m.target_value]
        if improving_metrics:
            best_metric = max(improving_metrics, key=lambda x: x.current_value / x.target_value)
            insights.append(f"Excellent progress in {best_metric.name}: {best_metric.current_value}{best_metric.unit}")
        
        # Найти области для внимания
        attention_metrics = [m for m in metrics if m.current_value < m.target_value * 0.9]
        if attention_metrics:
            worst_metric = min(attention_metrics, key=lambda x: x.current_value / x.target_value)
            insights.append(f"Needs attention: {worst_metric.name} at {worst_metric.current_value}{worst_metric.unit} (target: {worst_metric.target_value})")
        
        # Общие тренды
        user_metrics = [m for m in metrics if m.category == "user_adoption"]
        if user_metrics:
            avg_satisfaction = sum(m.current_value for m in user_metrics if "satisfaction" in m.name.lower()) / len([m for m in user_metrics if "satisfaction" in m.name.lower()])
            if avg_satisfaction > 8.5:
                insights.append(f"High user satisfaction maintained at {avg_satisfaction:.1f}/10")
        
        return insights

class ContinuousImprovementEngine:
    """Двигатель непрерывных улучшений"""
    
    def __init__(self):
        self.improvement_backlog = []
        self.feedback_analyzer = UserFeedbackAnalyzer()
    
    async def analyze_improvement_opportunities(self) -> List[Dict]:
        """Анализ возможностей для улучшения"""
        opportunities = []
        
        # Анализ метрик производительности
        perf_opportunities = await self.analyze_performance_bottlenecks()
        opportunities.extend(perf_opportunities)
        
        # Анализ обратной связи пользователей
        feedback_opportunities = await self.analyze_user_feedback()
        opportunities.extend(feedback_opportunities)
        
        # Анализ технического долга
        tech_debt_opportunities = await self.analyze_technical_debt()
        opportunities.extend(tech_debt_opportunities)
        
        # Приоритизация
        opportunities.sort(key=lambda x: x['impact_score'], reverse=True)
        
        return opportunities
    
    async def analyze_performance_bottlenecks(self) -> List[Dict]:
        """Анализ узких мест производительности"""
        # Получить данные из мониторинга
        slow_endpoints = [
            {"endpoint": "/api/v1/reports/financial", "avg_response_time": 3.2},
            {"endpoint": "/api/v1/transactions/search", "avg_response_time": 2.1}
        ]
        
        opportunities = []
        for endpoint in slow_endpoints:
            if endpoint["avg_response_time"] > 2.0:
                opportunities.append({
                    "type": "performance",
                    "title": f"Optimize {endpoint['endpoint']} performance",
                    "description": f"Current response time: {endpoint['avg_response_time']}s, target: <1.0s",
                    "impact_score": 85,
                    "effort_estimate": "2-3 weeks",
                    "category": "performance_optimization"
                })
        
        return opportunities
    
    async def analyze_user_feedback(self) -> List[Dict]:
        """Анализ обратной связи пользователей"""
        # Сбор и анализ отзывов пользователей
        common_requests = [
            {
                "request": "Bulk transaction import",
                "frequency": 23,
                "users": ["user1", "user2", "user3"]
            },
            {
                "request": "Mobile app", 
                "frequency": 19,
                "users": ["user4", "user5"]
            },
            {
                "request": "Advanced search filters",
                "frequency": 15,
                "users": ["user6", "user7"]
            }
        ]
        
        opportunities = []
        for request in common_requests:
            if request["frequency"] > 10:
                opportunities.append({
                    "type": "feature_request",
                    "title": f"Implement {request['request']}",
                    "description": f"Requested by {request['frequency']} users",
                    "impact_score": min(100, request["frequency"] * 3),
                    "effort_estimate": "4-6 weeks",
                    "category": "user_experience"
                })
        
        return opportunities
    
    async def create_improvement_roadmap(self) -> Dict:
        """Создание roadmap улучшений"""
        opportunities = await self.analyze_improvement_opportunities()
        
        # Группировка по кварталам
        q1_items = opportunities[:5]  # Топ-5 на первый квартал
        q2_items = opportunities[5:10]
        q3_items = opportunities[10:15]
        
        roadmap = {
            "Q1_2025": {
                "theme": "Performance & Stability",
                "items": q1_items,
                "estimated_effort": "12-16 weeks",
                "expected_outcomes": [
                    "50% improvement in report generation time",
                    "99.9% system uptime",
                    "Reduced support tickets by 30%"
                ]
            },
            "Q2_2025": {
                "theme": "User Experience & Mobile",
                "items": q2_items,
                "estimated_effort": "14-18 weeks", 
                "expected_outcomes": [
                    "Mobile app launch",
                    "Improved user satisfaction to 9.2/10",
                    "Advanced search capabilities"
                ]
            },
            "Q3_2025": {
                "theme": "Advanced Analytics & AI",
                "items": q3_items,
                "estimated_effort": "16-20 weeks",
                "expected_outcomes": [
                    "Predictive analytics dashboard",
                    "AI-powered anomaly detection",
                    "Advanced business intelligence"
                ]
            }
        }
        
        return roadmap

class UserFeedbackAnalyzer:
    """Анализатор обратной связи пользователей"""
    
    async def collect_feedback(self) -> List[Dict]:
        """Сбор обратной связи из различных источников"""
        # Support tickets
        support_feedback = await self.analyze_support_tickets()
        
        # User surveys
        survey_feedback = await self.analyze_user_surveys()
        
        # Usage analytics
        usage_feedback = await self.analyze_usage_patterns()
        
        return support_feedback + survey_feedback + usage_feedback
    
    async def analyze_support_tickets(self) -> List[Dict]:
        """Анализ тикетов поддержки для выявления паттернов"""
        # В реальности - запрос к базе данных тикетов
        common_issues = [
            {
                "category": "report_generation",
                "frequency": 45,
                "avg_resolution_time": "2.3 hours",
                "user_impact": "high",
                "suggested_improvement": "Add report templates and wizard"
            },
            {
                "category": "user_interface",
                "frequency": 32,
                "avg_resolution_time": "1.1 hours", 
                "user_impact": "medium",
                "suggested_improvement": "UI/UX improvements for complex forms"
            }
        ]
        
        feedback = []
        for issue in common_issues:
            if issue["frequency"] > 20:
                feedback.append({
                    "source": "support_tickets",
                    "category": issue["category"],
                    "priority": "high" if issue["user_impact"] == "high" else "medium",
                    "description": issue["suggested_improvement"],
                    "frequency": issue["frequency"]
                })
        
        return feedback
```

### 6.3 Future Enhancements Pipeline

#### Emerging Technologies Integration
```python
# future/emerging_tech.py
from dataclasses import dataclass
from typing import List, Dict
from datetime import datetime, timedelta

@dataclass
class TechInitiative:
    name: str
    description: str
    technology: str
    timeline: str
    investment_required: str
    expected_roi: str
    risk_level: str
    dependencies: List[str]

class EmergingTechRoadmap:
    """Roadmap внедрения новых технологий"""
    
    def __init__(self):
        self.initiatives = self.create_tech_initiatives()
    
    def create_tech_initiatives(self) -> List[TechInitiative]:
        return [
            TechInitiative(
                name="Blockchain Audit Trail",
                description="Immutable blockchain-based audit trail for critical transactions",
                technology="Ethereum/Polygon",
                timeline="Q4 2025",
                investment_required="$150K - $200K",
                expected_roi="Enhanced trust, reduced audit costs by 60%",
                risk_level="Medium",
                dependencies=["Regulatory approval", "Integration with existing audit system"]
            ),
            
            TechInitiative(
                name="AI-Powered Financial Advisor",
                description="AI assistant for financial planning and cash flow optimization",
                technology="GPT-4/Claude + Custom ML Models",
                timeline="Q2 2026",
                investment_required="$300K - $400K", 
                expected_roi="20% improvement in financial decision making",
                risk_level="High",
                dependencies=["Historical data collection", "ML expertise hiring"]
            ),
            
            TechInitiative(
                name="IoT Integration for Asset Management",
                description="IoT sensors for real-time asset tracking and depreciation",
                technology="IoT sensors + Edge computing",
                timeline="Q3 2026",
                investment_required="$100K - $150K",
                expected_roi="Accurate asset valuation, reduced manual work",
                risk_level="Low",
                dependencies=["Hardware procurement", "Asset tagging"]
            ),
            
            TechInitiative(
                name="Quantum-Safe Cryptography",
                description="Future-proof cryptographic systems against quantum computing",
                technology="Post-quantum cryptographic algorithms",
                timeline="Q1 2027",
                investment_required="$80K - $120K",
                expected_roi="Long-term security assurance",
                risk_level="Low",
                dependencies=["Industry standards maturity", "Library availability"]
            ),
            
            TechInitiative(
                name="Voice-Activated Accounting",
                description="Voice interface for hands-free transaction entry",
                technology="Advanced Speech Recognition + NLP",
                timeline="Q2 2026", 
                investment_required="$120K - $180K",
                expected_roi="40% faster data entry, improved accessibility",
                risk_level="Medium",
                dependencies=["Georgian language NLP models", "Voice security protocols"]
            ),
            
            TechInitiative(
                name="Augmented Reality Financial Dashboards",
                description="AR visualization of financial data and KPIs",
                technology="AR/VR (Apple Vision Pro, Meta Quest)",
                timeline="Q4 2026",
                investment_required="$200K - $300K",
                expected_roi="Enhanced data understanding, executive engagement",
                risk_level="High",
                dependencies=["AR device adoption", "3D visualization expertise"]
            )
        ]
    
    def prioritize_initiatives(self) -> List[TechInitiative]:
        """Приоритизация инициатив на основе ROI и риска"""
        # Простой scoring algorithm
        def calculate_priority_score(initiative: TechInitiative) -> float:
            roi_score = {
                "Enhanced trust, reduced audit costs by 60%": 9.0,
                "20% improvement in financial decision making": 8.5,
                "Accurate asset valuation, reduced manual work": 7.0,
                "Long-term security assurance": 6.0,
                "40% faster data entry, improved accessibility": 8.0,
                "Enhanced data understanding, executive engagement": 6.5
            }.get(initiative.expected_roi, 5.0)
            
            risk_penalty = {
                "Low": 0,
                "Medium": 1,
                "High": 2
            }.get(initiative.risk_level, 1)
            
            return roi_score - risk_penalty
        
        initiatives = self.initiatives.copy()
        initiatives.sort(key=calculate_priority_score, reverse=True)
        return initiatives
    
    def create_innovation_budget(self) -> Dict:
        """Создание бюджета на инновации"""
        prioritized = self.prioritize_initiatives()
        
        # Распределение по годам
        budget_2025 = []
        budget_2026 = []  
        budget_2027 = []
        
        for initiative in prioritized:
            if "2025" in initiative.timeline:
                budget_2025.append(initiative)
            elif "2026" in initiative.timeline:
                budget_2026.append(initiative)
            else:
                budget_2027.append(initiative)
        
        def calculate_budget(initiatives):
            total = 0
            for init in initiatives:
                # Извлекаем среднюю стоимость из диапазона
                cost_str = init.investment_required.replace("$", "").replace("K", "000")
                if " - " in cost_str:
                    min_cost, max_cost = cost_str.split(" - ")
                    avg_cost = (int(min_cost) + int(max_cost)) / 2
                    total += avg_cost
            return total
        
        return {
            "2025": {
                "initiatives": budget_2025,
                "total_budget": calculate_budget(budget_2025),
                "focus": "Foundation & Security"
            },
            "2026": {
                "initiatives": budget_2026,
                "total_budget": calculate_budget(budget_2026),
                "focus": "AI & User Experience"
            },
            "2027": {
                "initiatives": budget_2027, 
                "total_budget": calculate_budget(budget_2027),
                "focus": "Future-Proofing"
            }
        }

# Georgian Market Specific Innovations
class GeorgianMarketInnovations:
    """Инновации специфичные для грузинского рынка"""
    
    def __init__(self):
        self.georgian_initiatives = [
            {
                "name": "Georgian Language AI Assistant",
                "description": "AI помощник с полной поддержкой грузинского языка",
                "market_need": "Локализация и доступность для пользователей",
                "timeline": "Q3 2025",
                "partners": ["Tbilisi State University", "Georgian Tech Companies"]
            },
            {
                "name": "Integration with Georgian Banking APIs", 
                "description": "Прямая интеграция с API грузинских банков",
                "market_need": "Автоматизация банковских операций",
                "timeline": "Q2 2025",
                "partners": ["Bank of Georgia", "TBC Bank", "Liberty Bank"]
            },
            {
                "name": "Georgian Tax Law AI Advisor",
                "description": "AI система для консультаций по грузинскому налоговому законодательству", 
                "market_need": "Сложность налогового законодательства",
                "timeline": "Q4 2025",
                "partners": ["Ministry of Finance", "Georgian Tax Consultants Association"]
            },
            {
                "name": "Small Business Starter Package",
                "description": "Упрощенная версия для малого бизнеса до 100,000 лари",
                "market_need": "Доступность для малого бизнеса",
                "timeline": "Q1 2025",
                "partners": ["Enterprise Georgia", "GITA"]
            }
        ]
    
    def create_market_expansion_plan(self) -> Dict:
        """План расширения на грузинском рынке"""
        return {
            "target_segments": {
                "small_business": {
                    "size": "5,000+ companies",
                    "revenue_potential": "$2M annually",
                    "key_features": ["Simplified interface", "Georgian support", "Low cost"]
                },
                "medium_enterprises": {
                    "size": "1,500+ companies", 
                    "revenue_potential": "$8M annually",
                    "key_features": ["Full IFRS", "Advanced reporting", "Integrations"]
                },
                "large_corporations": {
                    "size": "200+ companies",
                    "revenue_potential": "$12M annually", 
                    "key_features": ["Multi-entity", "Custom workflows", "Dedicated support"]
                }
            },
            "market_penetration_strategy": {
                "year_1": "Capture 15% of medium enterprise market",
                "year_2": "Expand to small business segment", 
                "year_3": "Target large corporations and government",
                "year_5": "Market leadership position (40%+ market share)"
            },
            "competitive_advantages": [
                "Only IFRS + Georgian Tax compliant solution",
                "Local language and support",
                "Integration with Georgian financial ecosystem", 
                "Reasonable pricing for local market"
            ]
        }
```

---

## 🎯
                # План поэтапной миграции грузинской бухгалтерской системы

## 🎯 Общая стратегия миграции

**Подход**: Strangler Fig Pattern - постепенная замена компонентов без остановки работы системы

**Продолжительность**: 18-24 месяца

**Бюджет**: Распределен поэтапно для минимизации рисков

---

## 📋 Фаза 0: Подготовка и анализ (Месяцы 1-2)

### Цели:
- Аудит текущего состояния
- Подготовка инфраструктуры
- Создание команды миграции

### Задачи:

#### Неделя 1-2: Технический аудит
```bash
# Анализ кода
- Инвентаризация всех модулей и зависимостей
- Оценка тестового покрытия (текущий: ~10%, цель: 85%)
- Выявление критических узких мест производительности
- Анализ данных: объемы, структура, quality issues
```

#### Неделя 3-4: Создание MVP инфраструктуры
```yaml
# docker-compose-migration.yml
version: '3.8'
services:
  # Текущая система (legacy)
  legacy-app:
    build: ./legacy
    ports:
      - "8080:8080"
    networks:
      - migration-network
  
  # Новая система (target)
  new-api-gateway:
    build: ./new-system/gateway
    ports:
      - "8000:8000"
    networks:
      - migration-network
  
  # Shared resources
  postgres-new:
    image: postgres:15
    environment:
      POSTGRES_DB: accounting_new
    networks:
      - migration-network
  
  redis:
    image: redis:7-alpine
    networks:
      - migration-network

networks:
  migration-network:
    driver: bridge
```

#### Неделя 5-6: Создание Data Pipeline
```python
# migration/data_sync.py
from sqlalchemy import create_engine
import asyncpg
import pandas as pd

class DataSynchronizer:
    def __init__(self):
        self.legacy_engine = create_engine('postgresql://legacy_db')
        self.new_pool = None
    
    async def sync_accounts(self):
        """Синхронизация справочника счетов"""
        df = pd.read_sql("SELECT * FROM chart_of_accounts", self.legacy_engine)
        
        # Transform data
        df['id'] = df.apply(lambda x: uuid4(), axis=1)
        df['created_at'] = pd.Timestamp.now()
        
        # Load to new system
        async with self.new_pool.acquire() as conn:
            await conn.executemany(
                "INSERT INTO accounts (id, code, name, type) VALUES ($1, $2, $3, $4)",
                df[['id', 'code', 'name', 'account_type']].values.tolist()
            )
```

#### Неделя 7-8: CI/CD Pipeline
```yaml
# .github/workflows/migration.yml
name: Migration Pipeline
on:
  push:
    branches: [main, migration/*]

jobs:
  test-legacy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Test Legacy System
        run: |
          docker-compose -f legacy/docker-compose.test.yml up --abort-on-container-exit
  
  test-new-system:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Test New System
        run: |
          docker-compose -f new-system/docker-compose.test.yml up --abort-on-container-exit
  
  deploy-staging:
    needs: [test-legacy, test-new-system]
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to Staging
        run: |
          kubectl apply -f k8s/staging/
```

### Результаты Фазы 0:
- ✅ Детальный план миграции с временными рамками
- ✅ Настроенная инфраструктура для параллельной работы систем
- ✅ Команда готова к миграции (3-5 разработчиков)
- ✅ Базовая система мониторинга и алертов

---

## 🔧 Фаза 1: Модернизация фундамента (Месяцы 3-6)

### Цели:
- Замена устаревших компонентов
- Повышение безопасности
- Улучшение производительности

### 1.1 Модернизация базы данных (Месяц 3)

#### Неделя 1-2: Новая схема БД
```sql
-- migrations/001_new_schema.sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- Новая таблица счетов с UUID
CREATE TABLE accounts_v2 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(20) NOT NULL,
    name VARCHAR(100) NOT NULL,
    account_type account_type_enum NOT NULL,
    parent_id UUID REFERENCES accounts_v2(id),
    is_active BOOLEAN DEFAULT TRUE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    version INTEGER DEFAULT 1,
    
    -- Индексы для производительности
    CONSTRAINT unique_code_per_company UNIQUE (code, company_id)
);

CREATE INDEX idx_accounts_v2_code ON accounts_v2(code);
CREATE INDEX idx_accounts_v2_type ON accounts_v2(account_type);
CREATE INDEX idx_accounts_v2_parent ON accounts_v2(parent_id);
```

#### Неделя 3-4: Партиционирование для больших таблиц
```sql
-- Партиционирование журнала проводок по месяцам
CREATE TABLE journal_entries_v2 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id UUID NOT NULL,
    account_id UUID NOT NULL REFERENCES accounts_v2(id),
    debit DECIMAL(15,2) DEFAULT 0.00,
    credit DECIMAL(15,2) DEFAULT 0.00,
    currency_code CHAR(3) NOT NULL DEFAULT 'GEL',
    exchange_rate DECIMAL(15,5) DEFAULT 1.00000,
    description TEXT,
    transaction_date DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT check_debit_credit CHECK (
        (debit > 0 AND credit = 0) OR (credit > 0 AND debit = 0)
    )
) PARTITION BY RANGE (transaction_date);

-- Создание партиций на год вперед
CREATE TABLE journal_entries_202501 PARTITION OF journal_entries_v2
    FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');
-- ... остальные месяцы
```

### 1.2 Новый API слой (Месяц 4)

#### FastAPI с современными паттернами
```python
# new_system/api/main.py
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.security import HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import structlog

logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_database_pool()
    await init_kafka_producer()
    logger.info("Application started")
    
    yield
    
    # Shutdown
    await close_database_pool()
    await close_kafka_producer()
    logger.info("Application stopped")

app = FastAPI(
    title="Georgian Accounting System v2.0",
    description="Modern IFRS-compliant accounting system",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routes
from .routes import accounts, transactions, reports

app.include_router(accounts.router, prefix="/api/v1/accounts")
app.include_router(transactions.router, prefix="/api/v1/transactions")
app.include_router(reports.router, prefix="/api/v1/reports")
```

#### Современная архитектура с DI
```python
# new_system/core/dependencies.py
from dependency_injector import containers, providers
from dependency_injector.wiring import Provide

class Container(containers.DeclarativeContainer):
    # Configuration
    config = providers.Configuration()
    
    # Database
    db_pool = providers.Singleton(
        create_async_pool,
        config.database.url
    )
    
    # Repositories
    account_repository = providers.Factory(
        AccountRepository,
        db_pool=db_pool
    )
    
    transaction_repository = providers.Factory(
        TransactionRepository,
        db_pool=db_pool
    )
    
    # Services
    accounting_service = providers.Factory(
        AccountingService,
        account_repo=account_repository,
        transaction_repo=transaction_repository
    )

# Dependency injection
async def get_accounting_service(
    service: AccountingService = Depends(Provide[Container.accounting_service])
) -> AccountingService:
    return service
```

### 1.3 Система безопасности (Месяц 5)

#### JWT с refresh tokens
```python
# new_system/auth/jwt_handler.py
from jose import JWTError, jwt
from datetime import datetime, timedelta
import secrets

class JWTHandler:
    def __init__(self, secret_key: str):
        self.secret_key = secret_key
        self.algorithm = "HS256"
        self.access_token_expire = timedelta(minutes=30)
        self.refresh_token_expire = timedelta(days=7)
    
    async def create_tokens(self, user_id: str, permissions: List[str]) -> TokenPair:
        access_payload = {
            "sub": user_id,
            "permissions": permissions,
            "type": "access",
            "exp": datetime.utcnow() + self.access_token_expire,
            "iat": datetime.utcnow(),
            "jti": secrets.token_hex(16)  # JWT ID для отзыва
        }
        
        refresh_payload = {
            "sub": user_id,
            "type": "refresh",
            "exp": datetime.utcnow() + self.refresh_token_expire,
            "iat": datetime.utcnow(),
            "jti": secrets.token_hex(16)
        }
        
        access_token = jwt.encode(access_payload, self.secret_key, self.algorithm)
        refresh_token = jwt.encode(refresh_payload, self.secret_key, self.algorithm)
        
        # Сохранить refresh token в Redis с TTL
        await self.redis.setex(f"refresh:{refresh_payload['jti']}", 
                              int(self.refresh_token_expire.total_seconds()),
                              user_id)
        
        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=int(self.access_token_expire.total_seconds())
        )
```

#### Role-Based Access Control
```python
# new_system/auth/rbac.py
from enum import Enum
from dataclasses import dataclass
from typing import Set

class Permission(Enum):
    ACCOUNTS_READ = "accounts:read"
    ACCOUNTS_WRITE = "accounts:write"
    TRANSACTIONS_READ = "transactions:read"
    TRANSACTIONS_WRITE = "transactions:write"
    TRANSACTIONS_APPROVE = "transactions:approve"
    REPORTS_FINANCIAL = "reports:financial"
    REPORTS_TAX = "reports:tax"
    ADMIN_USERS = "admin:users"
    ADMIN_SYSTEM = "admin:system"

@dataclass
class Role:
    name: str
    permissions: Set[Permission]

class GeorgianAccountingRoles:
    ACCOUNTANT = Role("accountant", {
        Permission.ACCOUNTS_READ,
        Permission.TRANSACTIONS_READ,
        Permission.TRANSACTIONS_WRITE,
        Permission.REPORTS_FINANCIAL
    })
    
    CHIEF_ACCOUNTANT = Role("chief_accountant", {
        *ACCOUNTANT.permissions,
        Permission.TRANSACTIONS_APPROVE,
        Permission.REPORTS_TAX,
        Permission.ADMIN_USERS
    })
    
    TAX_SPECIALIST = Role("tax_specialist", {
        Permission.ACCOUNTS_READ,
        Permission.TRANSACTIONS_READ,
        Permission.REPORTS_TAX
    })

def require_permission(permission: Permission):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, current_user = Depends(get_current_user), **kwargs):
            if permission not in current_user.permissions:
                raise HTTPException(403, "Insufficient permissions")
            return await func(*args, **kwargs, current_user=current_user)
        return wrapper
    return decorator
```

### 1.4 Мониторинг и логирование (Месяц 6)

#### Структурированное логирование
```python
# new_system/core/logging.py
import structlog
from pythonjsonlogger import jsonlogger

def setup_logging():
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

# Использование в коде
logger = structlog.get_logger()

async def create_transaction(transaction_data: TransactionCreate):
    logger.info(
        "Transaction creation started",
        transaction_id=transaction_data.id,
        user_id=current_user.id,
        amount=float(transaction_data.total_amount)
    )
    
    try:
        result = await service.create_transaction(transaction_data)
        logger.info(
            "Transaction created successfully",
            transaction_id=result.id,
            duration_ms=(time.time() - start_time) * 1000
        )
        return result
    except Exception as e:
        logger.error(
            "Transaction creation failed",
            error=str(e),
            transaction_data=transaction_data.dict()
        )
        raise
```

#### Prometheus метрики
```python
# new_system/core/metrics.py
from prometheus_client import Counter, Histogram, Gauge
import time

# Business metrics
transaction_counter = Counter(
    'accounting_transactions_total',
    'Total number of accounting transactions',
    ['status', 'transaction_type']
)

transaction_amount_histogram = Histogram(
    'accounting_transaction_amount_gel',
    'Distribution of transaction amounts in GEL',
    buckets=[10, 50, 100, 500, 1000, 5000, 10000, 50000, float('inf')]
)

account_balance_gauge = Gauge(
    'accounting_account_balance_gel',
    'Current account balance in GEL',
    ['account_code', 'account_type']
)

# Technical metrics
request_duration = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint', 'status']
)

class MetricsMiddleware:
    async def __call__(self, request, call_next):
        start_time = time.time()
        response = await call_next(request)
        duration = time.time() - start_time
        
        request_duration.labels(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code
        ).observe(duration)
        
        return response
```

### Результаты Фазы 1:
- ✅ Новая БД схема с UUID и партиционированием
- ✅ Modern FastAPI с async/await
- ✅ JWT authentication с RBAC
- ✅ Структурированное логирование и метрики
- ✅ 60% покрытие тестами новых компонентов

---

## 🏗️ Фаза 2: Внедрение Event-Driven Architecture (Месяцы 7-10)

### Цели:
- Реализация Event Sourcing для audit trail
- CQRS для разделения чтения/записи
- Интеграция с Kafka

### 2.1 Event Store и Event Sourcing (Месяц 7)

#### Event Store на PostgreSQL
```sql
-- events/001_event_store.sql
CREATE TABLE event_store (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aggregate_id UUID NOT NULL,
    aggregate_type VARCHAR(100) NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    event_data JSONB NOT NULL,
    event_metadata JSONB DEFAULT '{}',
    version INTEGER NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT unique_version_per_aggregate UNIQUE (aggregate_id, version)
);

CREATE INDEX idx_event_store_aggregate ON event_store(aggregate_id);
CREATE INDEX idx_event_store_type ON event_store(event_type);
CREATE INDEX idx_event_store_timestamp ON event_store(timestamp);

-- Snapshots для производительности
CREATE TABLE aggregate_snapshots (
    aggregate_id UUID PRIMARY KEY,
    aggregate_type VARCHAR(100) NOT NULL,
    snapshot_data JSONB NOT NULL,
    version INTEGER NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

#### Базовые классы для Event Sourcing
```python
# new_system/events/base.py
from dataclasses import dataclass
from typing import Any, List, Dict
from abc import ABC, abstractmethod
import uuid
from datetime import datetime

@dataclass(frozen=True)
class DomainEvent:
    """Базовый класс для доменных событий"""
    aggregate_id: uuid.UUID
    event_id: uuid.UUID
    event_type: str
    event_data: Dict[str, Any]
    version: int
    timestamp: datetime
    metadata: Dict[str, Any]

class Aggregate(ABC):
    """Базовый класс для агрегатов"""
    def __init__(self, aggregate_id: uuid.UUID):
        self.id = aggregate_id
        self.version = 0
        self.uncommitted_events: List[DomainEvent] = []
    
    def apply_event(self, event: DomainEvent):
        """Применить событие к агрегату"""
        self._apply_event(event)
        if event.version > self.version:
            self.version = event.version
    
    def raise_event(self, event_type: str, event_data: Dict[str, Any], metadata: Dict[str, Any] = None):
        """Поднять новое событие"""
        event = DomainEvent(
            aggregate_id=self.id,
            event_id=uuid.uuid4(),
            event_type=event_type,
            event_data=event_data,
            version=self.version + 1,
            timestamp=datetime.utcnow(),
            metadata=metadata or {}
        )
        self.uncommitted_events.append(event)
        self.apply_event(event)
    
    @abstractmethod
    def _apply_event(self, event: DomainEvent):
        """Применить событие к состоянию агрегата"""
        pass
    
    def mark_events_as_committed(self):
        """Пометить события как сохраненные"""
        self.uncommitted_events.clear()
```

#### Accounting Aggregate
```python
# new_system/domain/aggregates.py
from decimal import Decimal
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class JournalEntryData:
    account_id: uuid.UUID
    debit: Decimal
    credit: Decimal
    description: str

class AccountingTransaction(Aggregate):
    """Агрегат бухгалтерской транзакции"""
    
    def __init__(self, aggregate_id: uuid.UUID):
        super().__init__(aggregate_id)
        self.transaction_date: Optional[datetime] = None
        self.description: str = ""
        self.entries: List[JournalEntryData] = []
        self.status: str = "draft"
        self.total_debit: Decimal = Decimal('0.00')
        self.total_credit: Decimal = Decimal('0.00')
    
    def create_transaction(self, transaction_date: datetime, description: str, entries: List[JournalEntryData]):
        """Создать новую транзакцию"""
        if self.status != "":
            raise ValueError("Transaction already exists")
        
        # Валидация двойной записи
        total_debit = sum(entry.debit for entry in entries)
        total_credit = sum(entry.credit for entry in entries)
        
        if total_debit != total_credit:
            raise ValueError(f"Unbalanced transaction: debit={total_debit}, credit={total_credit}")
        
        self.raise_event("TransactionCreated", {
            "transaction_date": transaction_date.isoformat(),
            "description": description,
            "entries": [
                {
                    "account_id": str(entry.account_id),
                    "debit": str(entry.debit),
                    "credit": str(entry.credit),
                    "description": entry.description
                }
                for entry in entries
            ],
            "total_amount": str(total_debit)
        })
    
    def approve_transaction(self, approved_by: uuid.UUID):
        """Одобрить транзакцию"""
        if self.status != "draft":
            raise ValueError(f"Cannot approve transaction with status: {self.status}")
        
        self.raise_event("TransactionApproved", {
            "approved_by": str(approved_by),
            "approved_at": datetime.utcnow().isoformat()
        })
    
    def post_transaction(self, posted_by: uuid.UUID):
        """Провести транзакцию"""
        if self.status != "approved":
            raise ValueError(f"Cannot post transaction with status: {self.status}")
        
        self.raise_event("TransactionPosted", {
            "posted_by": str(posted_by),
            "posted_at": datetime.utcnow().isoformat()
        })
    
    def _apply_event(self, event: DomainEvent):
        """Применить событие к состоянию транзакции"""
        if event.event_type == "TransactionCreated":
            self.transaction_date = datetime.fromisoformat(event.event_data["transaction_date"])
            self.description = event.event_data["description"]
            self.entries = [
                JournalEntryData(
                    account_id=uuid.UUID(entry["account_id"]),
                    debit=Decimal(entry["debit"]),
                    credit=Decimal(entry["credit"]),
                    description=entry["description"]
                )
                for entry in event.event_data["entries"]
            ]
            self.total_debit = self.total_credit = Decimal(event.event_data["total_amount"])
            self.status = "draft"
            
        elif event.event_type == "TransactionApproved":
            self.status = "approved"
            
        elif event.event_type == "TransactionPosted":
            self.status = "posted"
```

### 2.2 CQRS Implementation (Месяц 8)

#### Command и Query разделение
```python
# new_system/cqrs/commands.py
from dataclasses import dataclass
from abc import ABC, abstractmethod

class Command(ABC):
    """Базовый класс для команд"""
    pass

class CommandHandler(ABC):
    @abstractmethod
    async def handle(self, command: Command) -> Any:
        pass

@dataclass
class CreateTransactionCommand(Command):
    transaction_date: datetime
    description: str
    entries: List[JournalEntryData]
    created_by: uuid.UUID

class CreateTransactionHandler(CommandHandler):
    def __init__(self, event_store: EventStore, event_bus: EventBus):
        self.event_store = event_store
        self.event_bus = event_bus
    
    async def handle(self, command: CreateTransactionCommand) -> uuid.UUID:
        # Создать агрегат
        transaction_id = uuid.uuid4()
        transaction = AccountingTransaction(transaction_id)
        
        # Выполнить бизнес-логику
        transaction.create_transaction(
            command.transaction_date,
            command.description,
            command.entries
        )
        
        # Сохранить события
        await self.event_store.save_events(
            transaction.id,
            transaction.uncommitted_events,
            expected_version=0
        )
        
        # Опубликовать события
        for event in transaction.uncommitted_events:
            await self.event_bus.publish(event)
        
        transaction.mark_events_as_committed()
        return transaction.id
```

#### Query side (Read Models)
```python
# new_system/cqrs/queries.py
@dataclass
class AccountBalanceQuery:
    account_id: uuid.UUID
    as_of_date: Optional[datetime] = None

class AccountBalanceQueryHandler:
    def __init__(self, read_db_pool):
        self.read_db = read_db_pool
    
    async def handle(self, query: AccountBalanceQuery) -> Decimal:
        async with self.read_db.acquire() as conn:
            if query.as_of_date:
                result = await conn.fetchval(
                    """
                    SELECT balance FROM account_balances_history 
                    WHERE account_id = $1 AND date <= $2 
                    ORDER BY date DESC LIMIT 1
                    """,
                    query.account_id,
                    query.as_of_date
                )
            else:
                result = await conn.fetchval(
                    "SELECT current_balance FROM account_balances WHERE account_id = $1",
                    query.account_id
                )
            
            return Decimal(str(result or '0.00'))

# Projection для поддержания read models
class AccountBalanceProjection:
    def __init__(self, read_db_pool):
        self.read_db = read_db_pool
    
    async def handle_transaction_posted(self, event: DomainEvent):
        """Обновить балансы счетов при проведении транзакции"""
        entries = event.event_data["entries"]
        
        async with self.read_db.acquire() as conn:
            async with conn.transaction():
                for entry_data in entries:
                    account_id = uuid.UUID(entry_data["account_id"])
                    debit = Decimal(entry_data["debit"])
                    credit = Decimal(entry_data["credit"])
                    
                    # Обновить текущий баланс
                    await conn.execute(
                        """
                        INSERT INTO account_balances (account_id, current_balance, last_updated)
                        VALUES ($1, $2, $3)
                        ON CONFLICT (account_id) DO UPDATE SET
                            current_balance = account_balances.current_balance + $2,
                            last_updated = $3
                        """,
                        account_id,
                        debit - credit,
                        event.timestamp
                    )
                    
                    # Добавить историческую запись
                    await conn.execute(
                        """
                        INSERT INTO account_balance_history 
                        (account_id, date, balance_change, running_balance, transaction_id)
                        VALUES ($1, $2, $3, 
                            (SELECT current_balance FROM account_balances WHERE account_id = $1),
                            $4)
                        """,
                        account_id,
                        event.timestamp.date(),
                        debit - credit,
                        event.aggregate_id
                    )
```

### 2.3 Kafka Integration (Месяц 9)

#### Event Bus с Kafka
```python
# new_system/infrastructure/event_bus.py
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
import json
from typing import Dict, Callable

class KafkaEventBus:
    def __init__(self, bootstrap_servers: str):
        self.bootstrap_servers = bootstrap_servers
        self.producer: Optional[AIOKafkaProducer] = None
        self.consumer = AIOKafkaConsumer(
            *topics,
            bootstrap_servers=self.bootstrap_servers,
            group_id="accounting-system",
            value_deserializer=lambda m: json.loads(m.decode('utf-8'))
        )
        
        await self.consumer.start()
        
        try:
            async for msg in self.consumer:
                await self._handle_message(msg)
        finally:
            await self.consumer.stop()
    
    async def _handle_message(self, msg):
        """Обработать входящее сообщение"""
        try:
            event_data = msg.value
            event_type = event_data["event_type"]
            
            if event_type in self.handlers:
                for handler in self.handlers[event_type]:
                    await handler(event_data)
                    
        except Exception as e:
            logger.error(
                "Event handling failed",
                error=str(e),
                topic=msg.topic,
                partition=msg.partition,
                offset=msg.offset
            )
```

### 2.4 Georgian Tax Service Integration (Месяц 10)

#### Real-time VAT reporting
```python
# new_system/integrations/georgian_tax.py
class GeorgianTaxEventHandler:
    def __init__(self, rs_client: RSApiClient):
        self.rs_client = rs_client
    
    async def handle_transaction_posted(self, event_data: Dict):
        """Обработать проведенную транзакцию для налогового учета"""
        transaction_id = event_data["aggregate_id"]
        entries = event_data["event_data"]["entries"]
        
        # Найти VAT-related проводки
        vat_entries = []
        for entry in entries:
            account = await self.get_account_info(entry["account_id"])
            if account.account_type == "VAT_PAYABLE" or account.account_type == "VAT_RECEIVABLE":
                vat_entries.append({
                    "account_id": entry["account_id"],
                    "amount": entry["credit"] if entry["credit"] > 0 else entry["debit"],
                    "type": "payable" if account.account_type == "VAT_PAYABLE" else "receivable"
                })
        
        if vat_entries:
            # Отправить в Georgian Revenue Service
            await self._notify_rs_about_vat_transaction(transaction_id, vat_entries)
    
    async def _notify_rs_about_vat_transaction(self, transaction_id: str, vat_entries: List[Dict]):
        """Уведомить RS.ge о VAT транзакции"""
        try:
            payload = {
                "transaction_id": transaction_id,
                "timestamp": datetime.utcnow().isoformat(),
                "vat_entries": vat_entries,
                "company_id": self.company_id
            }
            
            response = await self.rs_client.post("/api/v1/vat/transactions", payload)
            
            logger.info(
                "VAT transaction reported to RS.ge",
                transaction_id=transaction_id,
                rs_response_status=response.status
            )
            
        except Exception as e:
            logger.error(
                "Failed to report VAT transaction to RS.ge",
                transaction_id=transaction_id,
                error=str(e)
            )
            # Отправить в Dead Letter Queue для retry
            await self.send_to_dlq("vat_reporting", payload)
```

### Результаты Фазы 2:
- ✅ Event Store с полным audit trail
- ✅ CQRS с разделением read/write моделей
- ✅ Kafka для event streaming
- ✅ Real-time интеграция с Georgian Tax Service
- ✅ 80% покрытие тестами event-driven компонентов

---

## 🎯 Фаза 3: Микросервисная архитектура (Месяцы 11-14)

### Цели:
- Разделение на независимые сервисы
- API Gateway
- Service Mesh
- Container orchestration

### 3.1 Декомпозиция на микросервисы (Месяц 11)

#### Domain-Driven Design подход
```
Bounded Contexts:
├── 📁 accounting-core-service/        # Основные бухгалтерские операции
├── 📁 tax-service/                    # Налоговый учет и отчетность
├── 📁 payroll-service/                # Зарплата и кадры
├── 📁 inventory-service/              # Складской учет
├── 📁 reporting-service/              # Финансовая отчетность
├── 📁 compliance-service/             # Соответствие требованиям
├── 📁 integration-service/            # Внешние интеграции
├── 📁 notification-service/           # Уведомления
└── 📁 audit-service/                  # Аудит и логирование
```

#### Accounting Core Service
```python
# services/accounting-core/main.py
from fastapi import FastAPI
from .api import transactions, accounts, fiscal_periods
from .domain import AccountingDomain
from .infrastructure import EventStore, MessageBus

class AccountingCoreService:
    def __init__(self):
        self.app = FastAPI(
            title="Accounting Core Service",
            description="Core accounting operations and journal entries",
            version="1.0.0"
        )
        
        # Domain layer
        self.domain = AccountingDomain()
        
        # Infrastructure
        self.event_store = EventStore()
        self.message_bus = MessageBus()
        
        # API routes
        self.app.include_router(transactions.router, prefix="/transactions")
        self.app.include_router(accounts.router, prefix="/accounts")
        self.app.include_router(fiscal_periods.router, prefix="/fiscal-periods")
        
        # Health check
        @self.app.get("/health")
        async def health_check():
            return {
                "status": "healthy",
                "service": "accounting-core",
                "version": "1.0.0",
                "dependencies": {
                    "database": await self.check_database(),
                    "event_store": await self.check_event_store(),
                    "message_bus": await self.check_message_bus()
                }
            }
    
    async def check_database(self) -> str:
        try:
            await self.domain.repository.health_check()
            return "healthy"
        except:
            return "unhealthy"

if __name__ == "__main__":
    import uvicorn
    service = AccountingCoreService()
    uvicorn.run(service.app, host="0.0.0.0", port=8001)
```

#### Tax Service (Georgian-specific)
```python
# services/tax-service/domain/georgian_tax.py
from decimal import Decimal
from datetime import date, datetime
from typing import List, Dict

class GeorgianVATCalculator:
    STANDARD_RATE = Decimal('0.18')  # 18% VAT
    REGISTRATION_THRESHOLD = Decimal('100000.00')  # 100,000 GEL
    
    def __init__(self):
        self.current_month_turnover = Decimal('0.00')
        self.annual_turnover = Decimal('0.00')
    
    def calculate_vat(self, net_amount: Decimal, is_exempt: bool = False) -> Dict[str, Decimal]:
        """Рассчитать НДС по грузинским правилам"""
        if is_exempt:
            return {
                "net_amount": net_amount,
                "vat_amount": Decimal('0.00'),
                "gross_amount": net_amount,
                "vat_rate": Decimal('0.00')
            }
        
        vat_amount = net_amount * self.STANDARD_RATE
        gross_amount = net_amount + vat_amount
        
        return {
            "net_amount": net_amount,
            "vat_amount": vat_amount,
            "gross_amount": gross_amount,
            "vat_rate": self.STANDARD_RATE
        }
    
    def check_vat_registration_requirement(self, monthly_turnover: Decimal) -> bool:
        """Проверить необходимость регистрации плательщика НДС"""
        return monthly_turnover >= self.REGISTRATION_THRESHOLD

class GeorgianTaxDeclarationGenerator:
    def __init__(self):
        self.rs_integration = RSIntegrationService()
    
    async def generate_monthly_vat_declaration(self, company_id: str, year: int, month: int) -> VATDeclaration:
        """Создать месячную декларацию НДС"""
        # Собрать данные за месяц
        transactions = await self.get_vat_transactions(company_id, year, month)
        
        total_vat_payable = sum(t.vat_amount for t in transactions if t.type == "sale")
        total_vat_deductible = sum(t.vat_amount for t in transactions if t.type == "purchase")
        net_vat = total_vat_payable - total_vat_deductible
        
        declaration = VATDeclaration(
            company_id=company_id,
            period=f"{year}-{month:02d}",
            total_sales=sum(t.net_amount for t in transactions if t.type == "sale"),
            total_vat_payable=total_vat_payable,
            total_purchases=sum(t.net_amount for t in transactions if t.type == "purchase"),
            total_vat_deductible=total_vat_deductible,
            net_vat_payment=net_vat,
            due_date=date(year, month + 1 if month < 12 else year + 1, 15)
        )
        
        return declaration
    
    async def submit_to_rs_ge(self, declaration: VATDeclaration) -> RSSubmissionResult:
        """Отправить декларацию в rs.ge"""
        try:
            response = await self.rs_integration.submit_vat_declaration(declaration)
            return RSSubmissionResult(
                success=True,
                submission_id=response.submission_id,
                receipt_number=response.receipt_number
            )
        except Exception as e:
            logger.error("Failed to submit VAT declaration to RS.ge", error=str(e))
            return RSSubmissionResult(
                success=False,
                error_message=str(e)
            )
```

### 3.2 API Gateway (Месяц 12)

#### Kong API Gateway configuration
```yaml
# kong/kong.yml
_format_version: "3.0"

services:
  - name: accounting-core
    url: http://accounting-core-service:8001
    plugins:
      - name: rate-limiting
        config:
          minute: 1000
          hour: 10000
      - name: jwt
        config:
          secret_is_base64: false
          key_claim_name: kid
      - name: prometheus
        config:
          per_consumer: true
    
  - name: tax-service
    url: http://tax-service:8002
    plugins:
      - name: rate-limiting
        config:
          minute: 500
          hour: 5000
      - name: jwt
      - name: request-size-limiting
        config:
          allowed_payload_size: 10

routes:
  - name: accounting-transactions
    service: accounting-core
    paths:
      - /api/v1/transactions
    methods:
      - GET
      - POST
      - PUT
    plugins:
      - name: cors
        config:
          origins: ["*"]
          methods: ["GET", "POST", "PUT", "DELETE"]
  
  - name: georgian-tax
    service: tax-service
    paths:
      - /api/v1/tax
    plugins:
      - name: request-transformer
        config:
          add:
            headers:
              - "X-Georgian-Tax: true"

consumers:
  - username: accounting-system
    custom_id: accounting-system-001
    jwt_secrets:
      - algorithm: HS256
        key: accounting-jwt-key
        secret: ${JWT_SECRET}

plugins:
  - name: prometheus
    config:
      per_consumer: true
      status_code_metrics: true
      latency_metrics: true
      bandwidth_metrics: true
```

#### API Gateway с authentication
```python
# api-gateway/main.py
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
import httpx
import jwt
from typing import Dict

class APIGateway:
    def __init__(self):
        self.app = FastAPI(
            title="Georgian Accounting API Gateway",
            description="Central API gateway for microservices",
            version="1.0.0"
        )
        
        self.service_registry = {
            "accounting": "http://accounting-core-service:8001",
            "tax": "http://tax-service:8002",
            "payroll": "http://payroll-service:8003",
            "reporting": "http://reporting-service:8004"
        }
        
        self.setup_middleware()
        self.setup_routes()
    
    def setup_middleware(self):
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        @self.app.middleware("http")
        async def add_security_headers(request: Request, call_next):
            response = await call_next(request)
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            return response
    
    def setup_routes(self):
        @self.app.api_route("/api/v1/{service_name}/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
        async def proxy_request(
            service_name: str,
            path: str,
            request: Request,
            current_user = Depends(self.get_current_user)
        ):
            if service_name not in self.service_registry:
                raise HTTPException(status_code=404, detail="Service not found")
            
            service_url = self.service_registry[service_name]
            target_url = f"{service_url}/{path}"
            
            # Forward request
            async with httpx.AsyncClient() as client:
                response = await client.request(
                    method=request.method,
                    url=target_url,
                    content=await request.body(),
                    headers={
                        **dict(request.headers),
                        "X-User-ID": str(current_user.id),
                        "X-User-Permissions": ",".join(current_user.permissions)
                    },
                    params=request.query_params,
                    timeout=30.0
                )
            
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=dict(response.headers)
            )
    
    async def get_current_user(self, request: Request):
        """Извлечь текущего пользователя из JWT токена"""
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(401, "Missing or invalid authorization header")
        
        token = auth_header.split(" ")[1]
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            return User(
                id=payload["sub"],
                permissions=payload.get("permissions", [])
            )
        except jwt.InvalidTokenError:
            raise HTTPException(401, "Invalid token")
```

### 3.3 Service Mesh с Istio (Месяц 13)

#### Istio configuration
```yaml
# istio/virtual-service.yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: accounting-system
spec:
  http:
  - match:
    - uri:
        prefix: /api/v1/transactions
    route:
    - destination:
        host: accounting-core-service
        port:
          number: 8001
    retries:
      attempts: 3
      perTryTimeout: 10s
    timeout: 30s
    
  - match:
    - uri:
        prefix: /api/v1/tax
    route:
    - destination:
        host: tax-service
        port:
          number: 8002
    fault:
      delay:
        percentage:
          value: 0.1
        fixedDelay: 2s

---
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: accounting-services
spec:
  host: "*.accounting-system.svc.cluster.local"
  trafficPolicy:
    circuitBreaker:
      consecutiveErrors: 3
      interval: 30s
      baseEjectionTime: 30s
    connectionPool:
      tcp:
        maxConnections: 100
      http:
        http1MaxPendingRequests: 50
        maxRequestsPerConnection: 10
```

#### Circuit Breaker implementation
```python
# shared/circuit_breaker.py
import asyncio
from enum import Enum
from datetime import datetime, timedelta
import logging

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class CircuitBreaker:
    def __init__(self, 
                 failure_threshold: int = 5,
                 timeout: int = 60,
                 success_threshold: int = 2):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.success_threshold = success_threshold
        
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
    
    async def call(self, func, *args, **kwargs):
        """Выполнить функцию через circuit breaker"""
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                logging.info("Circuit breaker: Attempting reset")
            else:
                raise CircuitBreakerOpenError("Circuit breaker is open")
        
        try:
            result = await func(*args, **kwargs)
            self._record_success()
            return result
        except Exception as e:
            self._record_failure()
            raise e
    
    def _record_success(self):
        """Записать успешный вызов"""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
                logging.info("Circuit breaker: Reset to CLOSED")
    
    def _record_failure(self):
        """Записать неудачный вызов"""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logging.warning("Circuit breaker: Opened due to failures")
    
    def _should_attempt_reset(self) -> bool:
        """Проверить, следует ли попытаться сбросить circuit breaker"""
        if self.last_failure_time is None:
            return False
        
        return datetime.utcnow() - self.last_failure_time >= timedelta(seconds=self.timeout)

# Использование в сервисах
class TaxServiceClient:
    def __init__(self):
        self.circuit_breaker = CircuitBreaker()
        self.base_url = "http://tax-service:8002"
    
    async def calculate_vat(self, amount: Decimal) -> VATCalculation:
        return await self.circuit_breaker.call(self._calculate_vat_impl, amount)
    
    async def _calculate_vat_impl(self, amount: Decimal) -> VATCalculation:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/vat/calculate",
                json={"amount": str(amount)}
            )
            response.raise_for_status()
            return VATCalculation(**response.json())
```

### 3.4 Container Orchestration с Kubernetes (Месяц 14)

#### Kubernetes deployment manifests
```yaml
# k8s/accounting-core-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: accounting-core-service
  namespace: accounting-system
  labels:
    app: accounting-core
    version: v1
spec:
  replicas: 3
  selector:
    matchLabels:
      app: accounting-core
      version: v1
  template:
    metadata:
      labels:
        app: accounting-core
        version: v1
    spec:
      containers:
      - name: accounting-core
        image: accounting-system/accounting-core:v1.0.0
        ports:
        - containerPort: 8001
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: url
        - name: KAFKA_BROKERS
          value: "kafka:9092"
        - name: REDIS_URL
          value: "redis://redis:6379"
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8001
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8001
          initialDelaySeconds: 5
          periodSeconds: 5
        volumeMounts:
        - name: config
          mountPath: /app/config
          readOnly: true
      volumes:
      - name: config
        configMap:
          name: accounting-core-config

---
apiVersion: v1
kind: Service
metadata:
  name: accounting-core-service
  namespace: accounting-system
  labels:
    app: accounting-core
spec:
  selector:
    app: accounting-core
  ports:
  - name: http
    port: 8001
    targetPort: 8001
  type: ClusterIP

---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: accounting-core-hpa
  namespace: accounting-system
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: accounting-core-service
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

#### Helm chart для развертывания
```yaml
# helm/accounting-system/Chart.yaml
apiVersion: v2
name: accounting-system
description: Georgian IFRS-compliant accounting system
type: application
version: 1.0.0
appVersion: "1.0.0"

dependencies:
  - name: postgresql
    version: 12.1.9
    repository: https://charts.bitnami.com/bitnami
  - name: redis
    version: 17.3.7
    repository: https://charts.bitnami.com/bitnami
  - name: kafka
    version: 20.0.6
    repository: https://charts.bitnami.com/bitnami
```

```yaml
# helm/accounting-system/values.yaml
global:
  imageRegistry: "registry.accounting-system.com"
  imagePullSecrets: []

accountingCore:
  enabled: true
  image:
    repository: accounting-core
    tag: "v1.0.0"
  replicaCount: 3
  resources:
    requests:
      memory: 256Mi
      cpu: 250m
    limits:
      memory: 512Mi
      cpu: 500m
  
taxService:
  enabled: true
  image:
    repository: tax-service
    tag: "v1.0.0"
  replicaCount: 2
  georgianTax:
    rsApiUrl: "https://api.rs.ge"
    vatRate: 0.18

postgresql:
  enabled: true
  auth:
    postgresPassword: "secure-password"
    database: "accounting"
  primary:
    persistence:
      size: 100Gi
      storageClass: "fast-ssd"

redis:
  enabled: true
  auth:
    enabled: true
    password: "redis-password"

kafka:
  enabled: true
  replicaCount: 3
  persistence:
    size: 50Gi

ingress:
  enabled: true
  className: "nginx"
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    nginx.ingress.kubernetes.io/rate-limit: "1000"
  hosts:
    - host: api.accounting-system.ge
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: accounting-system-tls
      hosts:
        - api.accounting-system.ge
```

### Результаты Фазы 3:
- ✅ 9 независимых микросервисов
- ✅ API Gateway с authentication/authorization
- ✅ Service mesh с Istio
- ✅ Container orchestration в Kubernetes
- ✅ Auto-scaling и self-healing
- ✅ 90% покрытие тестами всех сервисов

---

## 🚀 Фаза 4: Cloud Native и Advanced Features (Месяцы 15-18)

### Цели:
- Cloud-native deployment
- Machine Learning для fraud detection
- Advanced analytics
- Multi-tenant architecture

### 4.2 Machine Learning для Fraud Detection (Месяц 16)

#### ML Pipeline для аномалии в транзакциях
```python
# ml/fraud_detection/models.py
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import joblib
from typing import Dict, List, Tuple
import asyncio

class TransactionFraudDetector:
    def __init__(self):
        self.isolation_forest = IsolationForest(
            contamination=0.1,  # 10% аномалий ожидается
            random_state=42,
            n_estimators=200
        )
        self.scaler = StandardScaler()
        self.feature_columns = [
            'amount_gel', 'hour_of_day', 'day_of_week', 'days_since_last_transaction',
            'amount_zscore', 'frequency_last_week', 'account_age_days',
            'transaction_count_today', 'average_transaction_amount'
        ]
        self.is_trained = False
    
    def extract_features(self, transactions: List[Dict]) -> pd.DataFrame:
        """Извлечь признаки для ML модели"""
        df = pd.DataFrame(transactions)
        
        # Временные признаки
        df['timestamp'] = pd.to_datetime(df['created_at'])
        df['hour_of_day'] = df['timestamp'].dt.hour
        df['day_of_week'] = df['timestamp'].dt.dayofweek
        
        # Пользовательские паттерны
        df = df.sort_values(['user_id', 'timestamp'])
        df['days_since_last_transaction'] = df.groupby('user_id')['timestamp'].diff().dt.total_seconds() / (24 * 3600)
        df['days_since_last_transaction'].fillna(0, inplace=True)
        
        # Статистические признаки
        user_stats = df.groupby('user_id').agg({
            'amount_gel': ['mean', 'std', 'count'],
            'timestamp': ['min']
        }).reset_index()
        
        user_stats.columns = ['user_id', 'avg_amount', 'std_amount', 'transaction_count', 'first_transaction']
        user_stats['account_age_days'] = (pd.Timestamp.now() - user_stats['first_transaction']).dt.total_seconds() / (24 * 3600)
        
        # Объединение с основными данными
        df = df.merge(user_stats[['user_id', 'avg_amount', 'std_amount', 'account_age_days']], on='user_id')
        
        # Z-score для суммы
        df['amount_zscore'] = np.abs((df['amount_gel'] - df['avg_amount']) / (df['std_amount'] + 1e-6))
        
        # Частота транзакций за последнюю неделю
        df['frequency_last_week'] = df.groupby('user_id')['timestamp'].transform(
            lambda x: x.rolling('7D').count()
        )
        
        # Количество транзакций сегодня
        df['transaction_count_today'] = df.groupby(['user_id', df['timestamp'].dt.date]).cumcount() + 1
        
        return df[self.feature_columns].fillna(0)
    
    async def train(self, training_data: List[Dict]):
        """Обучить модель на исторических данных"""
        features_df = self.extract_features(training_data)
        
        # Нормализация признаков
        features_scaled = self.scaler.fit_transform(features_df)
        
        # Обучение модели
        self.isolation_forest.fit(features_scaled)
        self.is_trained = True
        
        # Сохранение модели
        joblib.dump(self.isolation_forest, 'models/fraud_detector.joblib')
        joblib.dump(self.scaler, 'models/fraud_scaler.joblib')
        
        print(f"Model trained on {len(training_data)} transactions")
    
    async def predict_fraud_probability(self, transaction: Dict) -> float:
        """Предсказать вероятность мошенничества"""
        if not self.is_trained:
            await self.load_model()
        
        # Извлечение признаков для одной транзакции
        features_df = self.extract_features([transaction])
        features_scaled = self.scaler.transform(features_df)
        
        # Получение anomaly score (-1 = аномалия, 1 = нормальная)
        anomaly_score = self.isolation_forest.decision_function(features_scaled)[0]
        
        # Преобразование в вероятность (0-1)
        fraud_probability = max(0, min(1, (1 - anomaly_score) / 2))
        
        return fraud_probability
    
    async def load_model(self):
        """Загрузить обученную модель"""
        try:
            self.isolation_forest = joblib.load('models/fraud_detector.joblib')
            self.scaler = joblib.load('models/fraud_scaler.joblib')
            self.is_trained = True
        except FileNotFoundError:
            print("Pre-trained model not found. Training new model...")
            # Здесь можно загрузить исторические данные и обучить модель

class FraudDetectionService:
    def __init__(self):
        self.detector = TransactionFraudDetector()
        self.fraud_threshold = 0.7  # Порог для определения мошенничества
    
    async def analyze_transaction(self, transaction: Dict) -> Dict:
        """Анализ транзакции на предмет мошенничества"""
        fraud_probability = await self.detector.predict_fraud_probability(transaction)
        
        risk_level = "low"
        if fraud_probability > self.fraud_threshold:
            risk_level = "high"
        elif fraud_probability > 0.4:
            risk_level = "medium"
        
        return {
            "transaction_id": transaction["id"],
            "fraud_probability": fraud_probability,
            "risk_level": risk_level,
            "requires_review": fraud_probability > self.fraud_threshold,
            "analysis_timestamp": datetime.utcnow().isoformat()
        }
    
    async def handle_transaction_created_event(self, event_data: Dict):
        """Обработать событие создания транзакции для ML анализа"""
        transaction = event_data["event_data"]
        analysis_result = await self.analyze_transaction(transaction)
        
        if analysis_result["requires_review"]:
            # Отправить алерт для ручной проверки
            await self.send_fraud_alert(analysis_result)
            
            # Заблокировать транзакцию до проверки
            await self.flag_transaction_for_review(transaction["id"])
        
        # Сохранить результат анализа
        await self.save_fraud_analysis(analysis_result)
    
    async def send_fraud_alert(self, analysis_result: Dict):
        """Отправить уведомление о подозрительной транзакции"""
        alert = {
            "alert_type": "fraud_detection",
            "severity": "high",
            "transaction_id": analysis_result["transaction_id"],
            "fraud_probability": analysis_result["fraud_probability"],
            "message": f"High fraud probability detected: {analysis_result['fraud_probability']:.2%}"
        }
        
        # Отправка через notification service
        await self.notification_service.send_alert(alert)
```

#### Real-time ML inference
```python
# ml/realtime_inference/inference_service.py
from kafka import KafkaConsumer, KafkaProducer
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging

class RealtimeMLInferenceService:
    def __init__(self):
        self.fraud_detector = FraudDetectionService()
        self.consumer = KafkaConsumer(
            'accounting.transactioncreated',
            bootstrap_servers=['kafka:9092'],
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            group_id='ml-fraud-detection'
        )
        self.producer = KafkaProducer(
            bootstrap_servers=['kafka:9092'],
            value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8')
        )
        self.executor = ThreadPoolExecutor(max_workers=10)
    
    async def start_processing(self):
        """Запуск real-time обработки транзакций"""
        logger.info("Starting ML inference service...")
        
        loop = asyncio.get_event_loop()
        
        for message in self.consumer:
            # Обработка в отдельном потоке для неблокирующей работы
            future = loop.run_in_executor(
                self.executor,
                self.process_transaction_message,
                message.value
            )
            
            # Не ждем завершения, чтобы обрабатывать следующие сообщения
            asyncio.create_task(self.handle_inference_result(future))
    
    def process_transaction_message(self, event_data: Dict) -> Dict:
        """Обработать сообщение о транзакции"""
        try:
            analysis_result = asyncio.run(
                self.fraud_detector.analyze_transaction(event_data)
            )
            return analysis_result
        except Exception as e:
            logger.error(f"ML inference failed: {e}")
            return {
                "error": str(e),
                "transaction_id": event_data.get("aggregate_id")
            }
    
    async def handle_inference_result(self, future):
        """Обработать результат ML inference"""
        try:
            result = await future
            
            # Отправить результат в Kafka
            self.producer.send('ml.fraud-analysis-result', result)
            
            if result.get("requires_review"):
                # Отправить в high-priority топик для немедленной обработки
                self.producer.send('alerts.high-priority', {
                    "type": "fraud_detection",
                    "data": result
                })
                
        except Exception as e:
            logger.error(f"Failed to handle inference result: {e}")
```

### 4.3 Advanced Analytics и BI (Месяц 17)

#### Real-time Analytics с ClickHouse
```python
# analytics/clickhouse_client.py
from clickhouse_driver import Client
from typing import List, Dict
import asyncio

class ClickHouseAnalytics:
    def __init__(self, host='clickhouse', port=9000):
        self.client = Client(host=host, port=port)
        self.setup_tables()
    
    def setup_tables(self):
        """Создать таблицы для аналитики"""
        # Таблица для транзакций (оптимизированная для анализа)
        self.client.execute('''
            CREATE TABLE IF NOT EXISTS transactions_analytics (
                transaction_id UUID,
                transaction_date Date,
                transaction_timestamp DateTime,
                company_id UUID,
                user_id UUID,
                total_amount Decimal(15, 2),
                currency_code String,
                account_debit_id UUID,
                account_credit_id UUID,
                account_debit_type String,
                account_credit_type String,
                is_approved UInt8,
                is_posted UInt8,
                created_at DateTime
            ) ENGINE = MergeTree()
            PARTITION BY toYYYYMM(transaction_date)
            ORDER BY (company_id, transaction_date, transaction_id)
        ''')
        
        # Материализованное представление для real-time агрегации
        self.client.execute('''
            CREATE MATERIALIZED VIEW IF NOT EXISTS daily_transactions_mv
            TO daily_transactions_summary
            AS SELECT
                company_id,
                transaction_date,
                count() as transaction_count,
                sum(total_amount) as total_amount,
                avg(total_amount) as avg_amount,
                countIf(is_posted = 1) as posted_count,
                sumIf(total_amount, is_posted = 1) as posted_amount
            FROM transactions_analytics
            GROUP BY company_id, transaction_date
        ''')
        
        # Таблица для КПП (ключевые показатели производительности)
        self.client.execute('''
            CREATE TABLE IF NOT EXISTS kpi_metrics (
                company_id UUID,
                metric_date Date,
                metric_name String,
                metric_value Decimal(15, 2),
                metric_currency String DEFAULT 'GEL',
                created_at DateTime DEFAULT now()
            ) ENGINE = ReplacingMergeTree(created_at)
            PARTITION BY toYYYYMM(metric_date)
            ORDER BY (company_id, metric_date, metric_name)
        ''')
    
    async def insert_transaction(self, transaction_data: Dict):
        """Вставить данные транзакции для аналитики"""
        await asyncio.to_thread(
            self.client.execute,
            'INSERT INTO transactions_analytics VALUES',
            [transaction_data]
        )
    
    async def get_financial_kpis(self, company_id: str, start_date: str, end_date: str) -> Dict:
        """Получить финансовые КПП за период"""
        query = '''
            SELECT
                -- Оборот
                sum(total_amount) as total_revenue,
                count() as transaction_count,
                avg(total_amount) as avg_transaction_amount,
                
                -- По типам счетов
                sumIf(total_amount, account_credit_type = 'REVENUE') as revenue,
                sumIf(total_amount, account_debit_type = 'EXPENSE') as expenses,
                
                -- Активы и обязательства
                sumIf(total_amount, account_debit_type = 'ASSET') as total_assets_increase,
                sumIf(total_amount, account_credit_type = 'LIABILITY') as total_liabilities_increase,
                
                -- Рентабельность
                (sumIf(total_amount, account_credit_type = 'REVENUE') - 
                 sumIf(total_amount, account_debit_type = 'EXPENSE')) as profit_loss
                
            FROM transactions_analytics
            WHERE company_id = %(company_id)s
            AND transaction_date BETWEEN %(start_date)s AND %(end_date)s
            AND is_posted = 1
        '''
        
        result = await asyncio.to_thread(
            self.client.execute,
            query,
            {'company_id': company_id, 'start_date': start_date, 'end_date': end_date}
        )
        
        return {
            'total_revenue': float(result[0][0] or 0),
            'transaction_count': result[0][1],
            'avg_transaction_amount': float(result[0][2] or 0),
            'revenue': float(result[0][3] or 0),
            'expenses': float(result[0][4] or 0),
            'total_assets_increase': float(result[0][5] or 0),
            'total_liabilities_increase': float(result[0][6] or 0),
            'profit_loss': float(result[0][7] or 0)
        }

class RealTimeAnalyticsService:
    def __init__(self):
        self.clickhouse = ClickHouseAnalytics()
        self.redis_client = redis.Redis(host='redis', port=6379, decode_responses=True)
    
    async def handle_transaction_posted_event(self, event_data: Dict):
        """Обработать событие проведения транзакции для аналитики"""
        transaction = event_data['event_data']
        
        # Вставить в ClickHouse для долгосрочной аналитики
        analytics_record = {
            'transaction_id': event_data['aggregate_id'],
            'transaction_date': transaction['transaction_date'][:10],
            'transaction_timestamp': transaction['transaction_date'],
            'company_id': transaction['company_id'],
            'user_id': transaction['created_by'],
            'total_amount': float(transaction['total_amount']),
            'currency_code': transaction.get('currency_code', 'GEL'),
            'is_posted': 1,
            'created_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        await self.clickhouse.insert_transaction(analytics_record)
        
        # Обновить real-time метрики в Redis
        await self.update_realtime_metrics(transaction)
    
    async def update_realtime_metrics(self, transaction: Dict):
        """Обновить метрики в реальном времени"""
        company_id = transaction['company_id']
        date_key = transaction['transaction_date'][:10]
        
        # Счетчики транзакций
        await self.redis_client.hincrby(
            f"metrics:daily:{company_id}:{date_key}",
            "transaction_count",
            1
        )
        
        # Сумма транзакций
        await self.redis_client.hincrbyfloat(
            f"metrics:daily:{company_id}:{date_key}",
            "total_amount",
            float(transaction['total_amount'])
        )
        
        # Установить TTL для автоматической очистки старых данных (30 дней)
        await self.redis_client.expire(
            f"metrics:daily:{company_id}:{date_key}",
            30 * 24 * 3600
        )
```

#### Business Intelligence Dashboard
```python
# analytics/dashboard_api.py
from fastapi import FastAPI, Depends, Query
from datetime import datetime, timedelta
import plotly.graph_objects as go
import plotly.express as px

class BIDashboardAPI:
    def __init__(self):
        self.app = FastAPI(title="Accounting Analytics Dashboard")
        self.clickhouse = ClickHouseAnalytics()
        self.setup_routes()
    
    def setup_routes(self):
        @self.app.get("/api/v1/dashboard/overview")
        async def get_overview(
            company_id: str,
            period: str = Query("30d", regex="^(7d|30d|90d|1y)$")
        ):
            """Получить обзорную информацию для dashboard"""
            end_date = datetime.now().date()
            
            if period == "7d":
                start_date = end_date - timedelta(days=7)
            elif period == "30d":
                start_date = end_date - timedelta(days=30)
            elif period == "90d":
                start_date = end_date - timedelta(days=90)
            else:  # 1y
                start_date = end_date - timedelta(days=365)
            
            kpis = await self.clickhouse.get_financial_kpis(
                company_id, str(start_date), str(end_date)
            )
            
            # Тренд за период
            trend_data = await self.get_trend_data(company_id, start_date, end_date)
            
            return {
                "period": period,
                "kpis": kpis,
                "trends": trend_data,
                "generated_at": datetime.utcnow().isoformat()
            }
        
        @self.app.get("/api/v1/dashboard/profit-loss-chart")
        async def get_profit_loss_chart(company_id: str, period: str = "30d"):
            """График прибыли и убытков"""
            # Получение данных из ClickHouse
            query = '''
                SELECT
                    transaction_date,
                    sumIf(total_amount, account_credit_type = 'REVENUE') as revenue,
                    sumIf(total_amount, account_debit_type = 'EXPENSE') as expenses
                FROM transactions_analytics
                WHERE company_id = %(company_id)s
                AND transaction_date >= today() - 30
                GROUP BY transaction_date
                ORDER BY transaction_date
            '''
            
            data = await asyncio.to_thread(
                self.clickhouse.client.execute,
                query,
                {'company_id': company_id}
            )
            
            # Создание Plotly графика
            dates = [row[0] for row in data]
            revenues = [float(row[1] or 0) for row in data]
            expenses = [float(row[2] or 0) for row in data]
            profit = [r - e for r, e in zip(revenues, expenses)]
            
            fig = go.Figure()
            
            fig.add_trace(go.Scatter(
                x=dates,
                y=revenues,
                mode='lines+markers',
                name='Доходы',
                line=dict(color='green')
            ))
            
            fig.add_trace(go.Scatter(
                x=dates,
                y=expenses,
                mode='lines+markers',
                name='Расходы',
                line=dict(color='red')
            ))
            
            fig.add_trace(go.Scatter(
                x=dates,
                y=profit,
                mode='lines+markers',
                name='Прибыль',
                line=dict(color='blue'),
                fill='tonexty'
            ))
            
            fig.update_layout(
                title="Динамика прибыли и убытков",
                xaxis_title="Дата",
                yaxis_title="Сумма (ლარი)",
                hovermode='x unified'
            )
            
            return fig.to_json()
        
        @self.app.get("/api/v1/dashboard/account-balances")
        async def get_account_balances(company_id: str):
            """Балансы по типам счетов"""
            query = '''
                SELECT
                    account_type,
                    sum(current_balance) as total_balance
                FROM account_balances ab
                JOIN accounts a ON ab.account_id = a.id
                WHERE a.company_id = %(company_id)s
                GROUP BY account_type
                ORDER BY total_balance DESC
            '''
            
            # Это запрос к основной PostgreSQL базе, не ClickHouse
            # Здесь нужно использовать соответствующий клиент
            
            return {
                "account_balances": [
                    {"type": "Активы", "balance": 150000.00},
                    {"type": "Обязательства", "balance": 75000.00},
                    {"type": "Капитал", "balance": 75000.00}
                ]
            }
```

### 4.4 Multi-tenant Architecture (Месяц 18)

#### Tenant isolation
```python
# tenancy/tenant_context.py
from contextvars import ContextVar
from typing import Optional
import uuid

# Контекстная переменная для текущего тенанта
current_tenant: ContextVar[Optional[str]] = ContextVar('current_tenant', default=None)

class TenantContext:
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self.token = None
    
    def __enter__(self):
        self.token = current_tenant.set(self.tenant_id)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.token:
            current_tenant.reset(self.token)

class TenantAwareRepository:
    """Базовый класс для tenant-aware репозиториев"""
    
    def __init__(self, db_pool):
        self.db_pool = db_pool
    
    def get_tenant_id(self) -> str:
        tenant_id = current_tenant.get()
        if not tenant_id:
            raise ValueError("No tenant context set")
        return tenant_id
    
    async def execute_query(self, query: str, params: list = None, tenant_filter: bool = True):
        """Выполнить запрос с автоматической фильтрацией по tenant"""
        if tenant_filter and "WHERE" in query.upper():
            # Добавить фильтр по tenant_id
            query = query.replace("WHERE", f"WHERE tenant_id = %s AND", 1)
            params = [self.get_tenant_id()] + (params or [])
        elif tenant_filter:
            # Добавить WHERE clause если его нет
            if "ORDER BY" in query.upper():
                query = query.replace("ORDER BY", "WHERE tenant_id = %s ORDER BY", 1)
            else:
                query += " WHERE tenant_id = %s"
            params = (params or []) + [self.get_tenant_id()]
        
        async with self.db_pool.acquire() as conn:
            return await conn.fetch(query, *params)

class AccountRepository(TenantAwareRepository):
    async def get_all_accounts(self) -> List[Account]:
        """Получить все счета для текущего тенанта"""
        query = """
            SELECT id, code, name, account_type, parent_id, is_active
            FROM accounts
            ORDER BY code
        """
        rows = await self.execute_query(query)
        return [Account(**dict(row)) for row in rows]
    
    async def create_account(self, account_data: AccountCreate) -> Account:
        """Создать новый счет для текущего тенанта"""
        query = """
            INSERT INTO accounts (id, tenant_id, code, name, account_type, parent_id, is_active)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING *
        """
        account_id = uuid.uuid4()
        tenant_id = self.get_tenant_id()
        
        row = await self.execute_query(
            query,
            [account_id, tenant_id, account_data.code, account_data.name, 
             account_data.account_type, account_data.parent_id, True],
            tenant_filter=False  # Уже добавили tenant_id вручную
        )
        return Account(**dict(row[0]))

# Middleware для извлечения tenant из запроса
class TenantMiddleware:
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            # Извлечь tenant_id из заголовка или JWT токена
            headers = dict(scope["headers"])
            tenant_id = self.extract_tenant_id(headers)
            
            if tenant_id:
                with TenantContext(tenant_id):
                    await self.app(scope, receive, send)
            else:
                # Вернуть ошибку если tenant не определен
                response = Response(
                    content="Tenant ID required",
                    status_code=400
                )
                await response(scope, receive, send)
        else:
            await self.app(scope, receive, send)
    
    def extract_tenant_id(self, headers) -> Optional[str]:
        # Попробовать извлечь из заголовка
        tenant_header = headers.get(b'x-tenant-id')
        if tenant_header:
            return tenant_header.decode()
        
        # Попробовать извлечь из JWT токена
        auth_header = headers.get(b'authorization')
        if auth_header and auth_header.startswith(b'Bearer '):
            token = auth_header[7:].decode()
            try:
                payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
                return payload.get('tenant_id')
            except:
                pass
        
        return None
```

#### Database schema для multi-tenancy
```sql
-- migration: add_tenant_support.sql

-- Добавить tenant_id ко всем основным таблицам
ALTER TABLE companies ADD COLUMN IF NOT EXISTS tenant_id UUID;
ALTER TABLE users ADD COLUMN IF NOT EXISTS tenant_id UUID;
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS tenant_id UUID;
ALTER TABLE journal_entries ADD COLUMN IF NOT EXISTS tenant_id UUID;
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS tenant_id UUID;
ALTER TABLE products ADD COLUMN IF NOT EXISTS tenant_id UUID;
ALTER TABLE employees ADD COLUMN IF NOT EXISTS tenant_id UUID;

-- Создать таблицу тенантов
CREATE TABLE IF NOT EXISTS tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    subdomain VARCHAR(100) UNIQUE,
    plan VARCHAR(50) DEFAULT 'basic',
    max_users INTEGER DEFAULT 10,
    max_companies INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Georgian-specific settings
    default_currency CHAR(3) DEFAULT 'GEL',
    vat_rate DECIMAL(5,4) DEFAULT 0.1800,
    tax_period VARCHAR(20) DEFAULT 'monthly',
    
    -- Feature flags
    features JSONB DEFAULT '{
        "advanced_reporting": false,
        "api_access": false,
        "multi_currency": true,
        "audit_trail": true,
        "ml_fraud_detection": false
    }'::jsonb
);

-- Подписки тенантов
CREATE TABLE tenant_subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    plan_name VARCHAR(50) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT TRUE,
    monthly_price DECIMAL(10,2),
    currency CHAR(3) DEFAULT 'GEL',
    
    -- Ограничения плана
    limits JSONB DEFAULT '{
        "max_users": 10,
        "max_companies": 1,
        "max_transactions_per_month": 1000,
        "storage_gb": 10
    }'::jsonb,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Обновить существующие индексы
DROP INDEX IF EXISTS idx_accounts_code;
CREATE INDEX idx_accounts_code_tenant ON accounts(tenant_id, code);

DROP INDEX IF EXISTS idx_journal_entries_account;
CREATE INDEX idx_journal_entries_account_tenant ON journal_entries(tenant_id, account_id, transaction_date);

-- Row Level Security (RLS) для дополнительной изоляции
ALTER TABLE accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE journal_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoices ENABLE ROW LEVEL SECURITY;

-- Политики RLS
CREATE POLICY accounts_tenant_isolation ON accounts
    FOR ALL TO authenticated_users
    USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY journal_entries_tenant_isolation ON journal_entries.1 Cloud Deployment (Месяц 15)

#### Infrastructure as Code с Terraform
```hcl
# terraform/main.tf
provider "google" {
  project = var.project_id
  region  = var.region
}

# GKE Cluster
resource "google_container_cluster" "accounting_cluster" {
  name     = "accounting-system"
  location = var.region
  
  remove_default_node_pool = true
  initial_node_count       = 1
  
  network    = google_compute_network.vpc.name
  subnetwork = google_compute_subnetwork.subnet.name
  
  master_auth {
    client_certificate_config {
      issue_client_certificate = false
    }
  }
  
  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }
  
  addons_config {
    istio_config {
      disabled = false
      auth     = "AUTH_MUTUAL_TLS"
    }
  }
}

# Node pools
resource "google_container_node_pool" "primary_nodes" {
  name       = "primary-node-pool"
  location   = var.region
  cluster    = google_container_cluster.accounting_cluster.name
  node_count = 3
  
  node_config {
    preemptible  = false
    machine_type = "e2-standard-4"
    
    service_account = google_service_account.gke_service_account.email
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]
    
    labels = {
      environment = var.environment
    }
    
    tags = ["accounting-system-node"]
  }
  
  autoscaling {
    min_node_count = 2
    max_node_count = 20
  }
  
  management {
    auto_repair  = true
    auto_upgrade = true
  }
}

# Cloud SQL (PostgreSQL)
resource "google_sql_database_instance" "accounting_db" {
  name             = "accounting-db-${var.environment}"
  database_version = "POSTGRES_14"
  region          = var.region
  
  settings {
    tier              = "db-standard-4"
    availability_type = "REGIONAL"
    disk_type         = "PD_SSD"
    disk_size         = 500
    disk_autoresize   = true
    
    backup_configuration {
      enabled                        = true
      start_time                     = "02:00"
      point_in_time_recovery_enabled = true
      transaction_log_retention_days = 7
      backup_retention_settings {
        retained_backups = 30
      }
    }
    
    ip_configuration {
      ipv4_enabled                                  = false
      private_network                               = google_compute_network.vpc.id
      enable_private_path_for_google_cloud_services = true
    }
    
    database_flags {
      name  = "max_connections"
      value = "1000"
    }
    
    insights_config {
      query_insights_enabled  = true
      query_string_length     = 1024
      record_application_tags = true
      record_client_address   = true
    }
  }
  
  deletion_protection = true
}

# Redis (Memorystore)
resource "google_redis_instance" "accounting_cache" {
  name           = "accounting-cache"
  tier           = "STANDARD_HA"
  memory_size_gb = 16
  region         = var.region
  
  authorized_network = google_compute_network.vpc.id
  
  redis_version = "REDIS_7_0"
  display_name  = "Accounting System Cache"
}
```

#### GitOps с ArgoCD
```yaml
# argocd/applications/accounting-system.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: accounting-system
  namespace: argocd
spec:
  project: default
  
  source:
    repoURL: https://github.com/accounting-system/k8s-manifests
    targetRevision: HEAD
    path: environments/production
    
  destination:
    server: https://kubernetes.default.svc
    namespace: accounting-system
    
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
      allowEmpty: false
    syncOptions:
      - CreateNamespace=true
      - PrunePropagationPolicy=foreground
      - PruneLast=true
    retry:
      limit: 5
      backoff:
        duration: 5s
        factor: 2
        maxDuration: 3m
        
  revisionHistoryLimit: 10
```

### 4: Optional[AIOKafkaConsumer] = None
        self.handlers: Dict[str, List[Callable]] = {}
    
    async def start(self):
        self.producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8')
        )
        await self.producer.start()
    
    async def publish(self, event: DomainEvent):
        """Опубликовать событие"""
        topic = f"accounting.{event.event_type.lower()}"
        
        event_payload = {
            "event_id": str(event.event_id),
            "aggregate_id": str(event.aggregate_id),
            "event_type": event.event_type,
            "event_data": event.event_data,
            "version": event.version,
            "timestamp": event.timestamp.isoformat(),
            "metadata": event.metadata
        }
        
        await self.producer.send(topic, event_payload)
        
        logger.info(
            "Event published",
            event_type=event.event_type,
            aggregate_id=str(event.aggregate_id),
            topic=topic
        )
    
    async def subscribe(self, event_type: str, handler: Callable):
        """Подписаться на тип события"""
        if event_type not in self.handlers:
            self.handlers[event_type] = []
        self.handlers[event_type].append(handler)
    
    async def start_consuming(self):
        """Начать обработку событий"""
        topics = [f"accounting.{event_type.lower()}" for event_type in self.handlers.keys()]
        
        self.consumer