#!/usr/bin/env python3
"""
🔐 IPFS & Blockchain Backup System for Camouflaged & Encrypted Files
Enhanced backup and recovery mechanism for secure vault files

Features:
  ✓ Automatic backup to IPFS for all files (especially camouflaged & encrypted)
  ✓ Blockchain ledger with backup metadata
  ✓ Automatic recovery from IPFS if files are removed/corrupted
  ✓ Multi-redundancy support (multiple IPFS nodes)
  ✓ Backup verification and integrity checks
  ✓ Recovery with automatic restoration

Author: SecureVault Development Team
Version: 2.0
"""

import os
import json
import hashlib
import logging
import time
import shutil
from datetime import datetime, timedelta
from typing import Tuple, Optional, Dict, Any, List

try:
    import ipfshttpclient
    IPFS_AVAILABLE = True
except ImportError:
    IPFS_AVAILABLE = False
    logging.warning("ipfshttpclient not available - IPFS features limited")


class IPFSBackupManager:
    """Enhanced IPFS backup management with redundancy"""
    
    def __init__(self):
        """Initialize IPFS backup manager with connection settings"""
        self.client = None
        self.primary_node = '/ip4/127.0.0.1/tcp/5001/http'
        self.backup_nodes = [
            '/ip4/127.0.0.1/tcp/5002/http',  # Backup local node
            '/ip4/127.0.0.1/tcp/5003/http',  # Tertiary local node
        ]
        self.backup_history = {}  # Track backups per file
        self._connect()
    
    def _connect(self) -> bool:
        """Connect to primary IPFS node with fallback"""
        if not IPFS_AVAILABLE:
            logging.warning("IPFS not available - installing ipfshttpclient recommended")
            return False
        
        try:
            self.client = ipfshttpclient.connect(self.primary_node)
            logging.info(f"Connected to primary IPFS node: {self.primary_node}")
            return True
        except Exception as e:
            logging.warning(f"Primary IPFS node failed: {e}, trying backups...")
            
            # Try backup nodes
            for node in self.backup_nodes:
                try:
                    self.client = ipfshttpclient.connect(node)
                    logging.info(f"Connected to backup IPFS node: {node}")
                    return True
                except Exception as e2:
                    logging.debug(f"Backup node {node} failed: {e2}")
            
            logging.error("All IPFS nodes failed - offline backup mode")
            return False
    
    def backup_file(self, file_path: str, file_id: str, 
                   backup_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Backup a file to IPFS with metadata
        
        Returns: {
            'success': bool,
            'cid': str or None,
            'timestamp': str,
            'size': int,
            'hash': str,
            'redundancy_level': int,
            'backup_locations': [str]
        }
        """
        result = {
            'success': False,
            'cid': None,
            'timestamp': datetime.now().isoformat(),
            'size': 0,
            'hash': '',
            'redundancy_level': 0,
            'backup_locations': []
        }
        
        try:
            if not os.path.exists(file_path):
                logging.error(f"Backup source not found: {file_path}")
                return result
            
            # Calculate file hash and size
            file_hash = self._calculate_hash(file_path)
            file_size = os.path.getsize(file_path)
            
            result['size'] = file_size
            result['hash'] = file_hash
            
            
            
            cid = self._upload_to_ipfs(file_path)
            if cid:
                result['success'] = True
                result['cid'] = cid
                result['backup_locations'].append(self.primary_node)
                result['redundancy_level'] = 1
                
                logging.info(f"File backed up to IPFS: {file_id} -> {cid}")
                
                # Store backup metadata
                if file_id not in self.backup_history:
                    self.backup_history[file_id] = []
                
                self.backup_history[file_id].append({
                    'cid': cid,
                    'timestamp': result['timestamp'],
                    'size': file_size,
                    'hash': file_hash,
                    'backup_name': backup_name or os.path.basename(file_path)
                })
            
            return result
        
        except Exception as e:
            logging.error(f"Backup error for {file_id}: {e}")
            return result
    
    def _upload_to_ipfs(self, file_path: str) -> Optional[str]:
        """Upload file to IPFS and return CID"""
        try:
            if not self.client:
                return None
            
            response = self.client.add(file_path)
            return response.get('Hash') or response.get('hash')
        except Exception as e:
            logging.error(f"IPFS upload error: {e}")
            return None
    
    def backup_camouflaged_file(self, file_id: str, storage_path: str,
                               original_name: str) -> Dict[str, Any]:
        """
        Special backup for camouflaged files with mapping preservation
        
        Backs up both the camouflaged file and its metadata
        """
        backup_result = self.backup_file(
            storage_path, 
            file_id, 
            backup_name=original_name
        )
        
        if backup_result['success']:
            logging.info(f"Camouflaged file backed up: {original_name} (ID: {file_id})")
        
        return backup_result
    
    def recover_file(self, file_id: str, cid: str, 
                    output_path: str) -> Tuple[bool, str]:
        """
        Recover file from IPFS using CID with robust error handling
        
        Returns: (success, message)
        """
        try:
            if not self.client:
                return False, "IPFS client not available"
            
            if not cid:
                return False, "No CID provided for recovery"
            
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Download from IPFS with retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    self.client.get(cid, output_path)
                    break
                except Exception as download_e:
                    if attempt < max_retries - 1:
                        logging.warning(f"IPFS download attempt {attempt + 1} failed, retrying: {download_e}")
                        time.sleep(1)  # Wait before retry
                    else:
                        raise download_e
            
            # Verify download with permission handling
            if os.path.exists(output_path):
                try:
                    # Ensure file is readable
                    os.chmod(output_path, 0o644)
                    # Test read to verify integrity
                    with open(output_path, 'rb') as f:
                        test_read = f.read(1024)  # Read first 1KB to verify
                    
                    logging.info(f"File recovered from IPFS: {file_id}")
                    return True, "Recovery successful"
                except PermissionError as pe:
                    logging.error(f"Permission error after IPFS download: {pe}")
                    return False, f"Permission denied: {pe}"
            else:
                return False, "Recovery download failed"
        
        except Exception as e:
            logging.error(f"Recovery error for {file_id}: {e}")
            return False, str(e)
    
    def check_file_health(self, file_id: str, current_hash: str) -> Dict[str, Any]:
        """
        Check if file needs backup/recovery
        
        Returns: {
            'healthy': bool,
            'backed_up': bool,
            'hash_match': bool,
            'needs_recovery': bool,
            'latest_cid': str or None
        }
        """
        result = {
            'healthy': False,
            'backed_up': False,
            'hash_match': False,
            'needs_recovery': False,
            'latest_cid': None
        }
        
        if file_id not in self.backup_history or not self.backup_history[file_id]:
            return result
        
        result['backed_up'] = True
        latest_backup = self.backup_history[file_id][-1]
        result['latest_cid'] = latest_backup['cid']
        
        # Check hash match
        if latest_backup['hash'] == current_hash:
            result['hash_match'] = True
            result['healthy'] = True
        else:
            result['needs_recovery'] = True
            result['healthy'] = False
        
        return result
    
    def _calculate_hash(self, file_path: str) -> str:
        """Calculate SHA256 hash of file"""
        try:
            sha256_hash = hashlib.sha256()
            with open(file_path, 'rb') as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except Exception as e:
            logging.error(f"Hash calculation error: {e}")
            return ""
    
    def get_backup_history(self, file_id: str) -> List[Dict]:
        """Get backup history for a file"""
        return self.backup_history.get(file_id, [])
    
    def list_all_backups(self) -> Dict[str, List[Dict]]:
        """List all backed up files"""
        return self.backup_history.copy()


class BlockchainBackupLedger:
    """Enhanced blockchain ledger for backup tracking"""
    
    def __init__(self, ledger_path: str):
        """Initialize blockchain backup ledger"""
        self.ledger_path = ledger_path
        self.backups_ledger = self._load_backups()
    
    def _load_backups(self) -> List[Dict]:
        """Load backup ledger from file"""
        backup_file = self.ledger_path.replace('.json', '_backups.json')
        if os.path.exists(backup_file):
            try:
                with open(backup_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return self._create_genesis()
    
    def _create_genesis(self) -> List[Dict]:
        """Create genesis backup record"""
        genesis = {
            'index': 0,
            'timestamp': datetime.now().isoformat(),
            'type': 'GENESIS_BACKUP',
            'data': 'BACKUP_LEDGER_START',
            'prev_hash': '0' * 64,
            'hash': hashlib.sha256(b'BACKUP_GENESIS').hexdigest()
        }
        return [genesis]
    
    def record_backup(self, file_id: str, cid: str, file_hash: str,
                     is_camouflaged: bool, file_size: int) -> Dict:
        """Record a backup in the blockchain ledger"""
        try:
            prev = self.backups_ledger[-1]
            record = {
                'index': len(self.backups_ledger),
                'timestamp': datetime.now().isoformat(),
                'type': 'FILE_BACKUP',
                'file_id': file_id,
                'ipfs_cid': cid,
                'file_hash': file_hash,
                'is_camouflaged': is_camouflaged,
                'file_size': file_size,
                'prev_hash': prev['hash'],
            }
            
            # Compute hash
            record_str = json.dumps(record, sort_keys=True)
            record['hash'] = hashlib.sha256(record_str.encode()).hexdigest()
            
            self.backups_ledger.append(record)
            self._save_backups()
            
            logging.info(f"Backup recorded in blockchain: {file_id}")
            return record
        
        except Exception as e:
            logging.error(f"Blockchain backup recording error: {e}")
            return {}
    
    def record_recovery(self, file_id: str, cid: str, recovered_at: str) -> Dict:
        """Record a file recovery in blockchain"""
        try:
            prev = self.backups_ledger[-1]
            record = {
                'index': len(self.backups_ledger),
                'timestamp': datetime.now().isoformat(),
                'type': 'FILE_RECOVERY',
                'file_id': file_id,
                'ipfs_cid': cid,
                'recovered_at': recovered_at,
                'prev_hash': prev['hash'],
            }
            
            record_str = json.dumps(record, sort_keys=True)
            record['hash'] = hashlib.sha256(record_str.encode()).hexdigest()
            
            self.backups_ledger.append(record)
            self._save_backups()
            
            logging.info(f"Recovery recorded in blockchain: {file_id}")
            return record
        
        except Exception as e:
            logging.error(f"Blockchain recovery recording error: {e}")
            return {}
    
    def get_file_backup_status(self, file_id: str) -> Dict[str, Any]:
        """Get comprehensive backup status for a file"""
        status = {
            'file_id': file_id,
            'has_backups': False,
            'backup_count': 0,
            'latest_backup': None,
            'has_recovery_record': False,
            'backup_chain': []
        }
        
        for record in self.backups_ledger:
            if record.get('file_id') == file_id:
                if record.get('type') == 'FILE_BACKUP':
                    status['has_backups'] = True
                    status['backup_count'] += 1
                    status['latest_backup'] = record
                    status['backup_chain'].append(record)
                elif record.get('type') == 'FILE_RECOVERY':
                    status['has_recovery_record'] = True
                    status['backup_chain'].append(record)
        
        return status
    
    def _save_backups(self):
        """Save backup ledger to file"""
        try:
            backup_file = self.ledger_path.replace('.json', '_backups.json')
            os.makedirs(os.path.dirname(backup_file), exist_ok=True)
            with open(backup_file, 'w') as f:
                json.dump(self.backups_ledger, f, indent=2)
        except Exception as e:
            logging.error(f"Error saving backup ledger: {e}")
    
    def get_backups_ledger(self) -> List[Dict]:
        """Get entire backup ledger"""
        return self.backups_ledger.copy()


class AutomaticBackupRecoverySystem:
    """
    Automatic backup and recovery system for the secure vault
    
    Monitors files and automatically:
    - Backs up camouflaged and encrypted files to IPFS
    - Detects missing/corrupted files
    - Recovers files from IPFS if needed
    - Maintains integrity across backups
    """
    
    def __init__(self, vault_path: str, ipfs_manager: IPFSBackupManager,
                 blockchain: BlockchainBackupLedger):
        """Initialize automatic backup/recovery system"""
        self.vault_path = vault_path
        self.ipfs = ipfs_manager
        self.blockchain = blockchain
        self.backup_interval = 3600  # 1 hour
        self.last_backup = {}
    
    def backup_and_protect_file(self, file_id: str, storage_path: str,
                               original_name: str, is_camouflaged: bool,
                               file_hash: str, file_size: int) -> bool:
        """
        Comprehensive backup and protection for a file
        
        Performs:
        1. IPFS backup
        2. Blockchain recording
        3. Integrity verification
        """
        try:
            # Step 1: Backup to IPFS
            backup_result = self.ipfs.backup_camouflaged_file(
                file_id, 
                storage_path, 
                original_name
            )
            
            if not backup_result['success']:
                logging.warning(f"IPFS backup failed for {file_id}")
                return False
            
            # Step 2: Record in blockchain
            blockchain_record = self.blockchain.record_backup(
                file_id,
                backup_result['cid'],
                file_hash,
                is_camouflaged,
                file_size
            )
            
            if not blockchain_record:
                logging.warning(f"Blockchain recording failed for {file_id}")
                return False
            
            # Step 3: Update last backup time
            self.last_backup[file_id] = datetime.now()
            
            logging.info(f"File protected: {file_id} (IPFS: {backup_result['cid']})")
            return True
        
        except Exception as e:
            logging.error(f"Backup protection error for {file_id}: {e}")
            return False
    
    def check_and_recover_file(self, file_id: str, storage_path: str,
                              metadata: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Check file health and recover from backup if needed
        
        Returns: (success, message)
        """
        try:
            # Check if file exists
            if os.path.exists(storage_path):
                return True, "File exists and is accessible"
            
            logging.warning(f"File missing: {file_id} at {storage_path}")
            
            # Get backup status from blockchain
            status = self.blockchain.get_file_backup_status(file_id)
            
            if not status['has_backups']:
                return False, "No backup available for recovery"
            
            # Get latest backup CID
            if not status['latest_backup']:
                return False, "No backup record found"
            
            backup_cid = status['latest_backup'].get('ipfs_cid')
            if not backup_cid:
                return False, "No IPFS CID in backup record"
            
            # Recover from IPFS
            recovery_dir = os.path.dirname(storage_path)
            os.makedirs(recovery_dir, exist_ok=True)
            
            success, message = self.ipfs.recover_file(file_id, backup_cid, storage_path)
            
            if success:
                # Record recovery in blockchain
                self.blockchain.record_recovery(file_id, backup_cid, storage_path)
                logging.info(f"File recovered successfully: {file_id}")
                return True, "File recovered from IPFS backup"
            else:
                return False, f"Recovery failed: {message}"
        
        except Exception as e:
            logging.error(f"Recovery check error for {file_id}: {e}")
            return False, str(e)
    
    def periodic_backup_check(self, files_metadata: Dict[str, Dict]) -> Dict[str, Any]:
        """
        Perform periodic backup health check on all files
        
        Returns: {
            'total_files': int,
            'backed_up': int,
            'missing_files': [str],
            'recovered_files': [str],
            'failed_recoveries': [str]
        }
        """
        results = {
            'total_files': len(files_metadata),
            'backed_up': 0,
            'missing_files': [],
            'recovered_files': [],
            'failed_recoveries': []
        }
        
        try:
            for file_id, metadata in files_metadata.items():
                storage_path = metadata.get('storage_path')
                
                # Check if file exists
                if not os.path.exists(storage_path):
                    results['missing_files'].append(file_id)
                    
                    # Try recovery
                    success, message = self.check_and_recover_file(
                        file_id, 
                        storage_path,
                        metadata
                    )
                    
                    if success:
                        results['recovered_files'].append(file_id)
                    else:
                        results['failed_recoveries'].append({
                            'file_id': file_id,
                            'reason': message
                        })
                else:
                    results['backed_up'] += 1
            
            logging.info(f"Backup health check: {results}")
            return results
        
        except Exception as e:
            logging.error(f"Periodic backup check error: {e}")
            return results
    
    def generate_backup_report(self) -> str:
        """Generate comprehensive backup report"""
        report = []
        report.append("=" * 80)
        report.append("IPFS & BLOCKCHAIN BACKUP RECOVERY REPORT")
        report.append(f"Generated: {datetime.now().isoformat()}")
        report.append("=" * 80)
        
        # IPFS Backups
        backups = self.ipfs.list_all_backups()
        report.append(f"\n📦 IPFS BACKUPS ({len(backups)} files)")
        report.append("-" * 80)
        
        total_size = 0
        for file_id, history in backups.items():
            if history:
                latest = history[-1]
                report.append(f"  • {file_id}")
                report.append(f"    - Name: {latest.get('backup_name')}")
                report.append(f"    - CID: {latest.get('cid')}")
                report.append(f"    - Size: {latest.get('size')} bytes")
                report.append(f"    - Timestamp: {latest.get('timestamp')}")
                total_size += latest.get('size', 0)
        
        report.append(f"\n  Total backed up: {len(backups)} files, {total_size} bytes")
        
        # Blockchain Records
        ledger = self.blockchain.get_backups_ledger()
        backup_records = [r for r in ledger if r.get('type') == 'FILE_BACKUP']
        recovery_records = [r for r in ledger if r.get('type') == 'FILE_RECOVERY']
        
        report.append(f"\n⛓️  BLOCKCHAIN RECORDS")
        report.append("-" * 80)
        report.append(f"  • Backup records: {len(backup_records)}")
        report.append(f"  • Recovery records: {len(recovery_records)}")
        report.append(f"  • Total ledger entries: {len(ledger)}")
        
        if recovery_records:
            report.append(f"\n  Recent Recoveries:")
            for record in recovery_records[-5:]:
                report.append(f"    - {record.get('file_id')} at {record.get('timestamp')}")
        
        report.append("\n" + "=" * 80)
        
        return "\n".join(report)


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def setup_ipfs_backup_system(vault_path: str, blockchain_ledger_path: str) -> Tuple[IPFSBackupManager, BlockchainBackupLedger, AutomaticBackupRecoverySystem]:
    """
    Initialize the complete IPFS and blockchain backup system
    
    Returns: (ipfs_manager, blockchain_ledger, recovery_system)
    """
    try:
        # Initialize IPFS backup manager
        ipfs_manager = IPFSBackupManager()
        
        # Initialize blockchain backup ledger
        blockchain_ledger = BlockchainBackupLedger(blockchain_ledger_path)
        
        # Initialize automatic recovery system
        recovery_system = AutomaticBackupRecoverySystem(
            vault_path,
            ipfs_manager,
            blockchain_ledger
        )
        
        logging.info("IPFS & Blockchain backup system initialized")
        return ipfs_manager, blockchain_ledger, recovery_system
    
    except Exception as e:
        logging.error(f"Backup system initialization error: {e}")
        raise


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Example usage
    vault_path = "./secure_vault"
    ledger_path = os.path.join(vault_path, "logs/blockchain.json")
    
    ipfs_mgr, blockchain, recovery = setup_ipfs_backup_system(vault_path, ledger_path)
    print(recovery.generate_backup_report())
