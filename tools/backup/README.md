# Backup Utility

Скрипты в этой папке создают безопасный архив текущего состояния репозитория без включения секретов.

## Команды

# Локальная проверка (сухой прогон)
pwsh -File tools/backup/backup.ps1 -DryRun

# Локальный бэкап
pwsh -File tools/backup/backup.ps1 -Label "pre-change"

# Запуск в GitHub Actions
gh workflow run manual-backup.yml -f label=pre-change
