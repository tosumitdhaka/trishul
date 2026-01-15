# scripts/backup.sh
#!/bin/bash
BACKUP_DIR="/mnt/c/Testing/trishul/backup/$(date +%Y%m%d-%H%M%S)"
mkdir -p $BACKUP_DIR

echo "Backing up to $BACKUP_DIR"

# MySQL
kubectl exec -n trishul trishul-mysql-0 -- mysqldump -uroot -ptrishul123 --all-databases > $BACKUP_DIR/mysql.sql

# Helm values
helm get values trishul -n trishul > $BACKUP_DIR/values.yaml

echo "Backup complete!"
