# init_db.py - Clean Database Initialization
from app import create_app, db
from app.auth.models import User
from app.modules.models import Module, ModuleCategory
from app.terminal.models import TerminalSession, TerminalLog, TerminalLogSummary
from app.core.models import SystemLog, LogSearchQuery, SystemMetric
from datetime import datetime

def initialize_database():
    """Initialize the CoreSecFrame database with clean structure"""
    
    app = create_app()
    
    with app.app_context():
        print("🚀 CoreSecFrame Database Initialization")
        print("=" * 50)
        
        # Drop all tables and recreate
        print("🗑️  Dropping all existing tables...")
        db.drop_all()
        
        print("🏗️  Creating all database tables...")
        db.create_all()
        
        # Verify all tables were created
        inspector = db.inspect(db.engine)
        tables = inspector.get_table_names()
        
        expected_tables = [
            'user', 'module', 'module_category', 
            'terminal_session', 'terminal_log', 'terminal_log_summary',
            'system_log', 'log_search_query', 'system_metric'
        ]
        
        print("\n📊 Database Tables Created:")
        for table in expected_tables:
            if table in tables:
                print(f"  ✅ {table}")
            else:
                print(f"  ❌ {table} - MISSING!")
        
        # Create essential users
        print("\n👥 Creating essential users...")
        
        # Admin user
        admin = User(
            username='admin', 
            email='admin@coresecframe.local', 
            role='admin',
            created_at=datetime.utcnow()
        )
        admin.set_password('admin')
        db.session.add(admin)
        print("  ✅ Admin user (admin/admin)")
        
        # Regular user
        user = User(
            username='user', 
            email='user@coresecframe.local', 
            role='user',
            created_at=datetime.utcnow()
        )
        user.set_password('password')
        db.session.add(user)
        print("  ✅ Regular user (user/password)")
        
        # Create module categories
        print("\n📂 Creating module categories...")
        categories = [
            ModuleCategory(
                name='Reconnaissance',
                description='Information gathering and target discovery tools'
            ),
            ModuleCategory(
                name='Vulnerability Analysis',
                description='Security vulnerability scanning and analysis tools'
            ),
            ModuleCategory(
                name='Exploitation',
                description='Penetration testing and exploitation frameworks'
            ),
            ModuleCategory(
                name='Post Exploitation',
                description='Post-exploitation and persistence tools'
            ),
            ModuleCategory(
                name='Reporting',
                description='Report generation and documentation tools'
            ),
            ModuleCategory(
                name='Utils',
                description='Utility tools and helper scripts'
            )
        ]
        
        for category in categories:
            db.session.add(category)
            print(f"  ✅ {category.name}")
        
        # Commit the changes
        print("\n💾 Committing changes to database...")
        db.session.commit()
        
        # Verify data was created
        user_count = User.query.count()
        category_count = ModuleCategory.query.count()
        
        print("\n📈 Database Statistics:")
        print(f"  • Users: {user_count}")
        print(f"  • Module Categories: {category_count}")
        print(f"  • Modules: 0 (ready for scanning)")
        print(f"  • Terminal Sessions: 0 (ready for use)")
        print(f"  • System Logs: 0 (ready for logging)")
        
        print("\n🎉 Database initialization completed successfully!")
        
        print("\n📋 Database Schema Summary:")
        print("  Authentication & Users:")
        print("    ✓ user - User accounts and authentication")
        print("  ")
        print("  Module Management:")
        print("    ✓ module_category - Security tool categories")
        print("    ✓ module - Security modules and tools")
        print("  ")
        print("  Terminal System:")
        print("    ✓ terminal_session - Terminal session management")
        print("    ✓ terminal_log - Detailed terminal activity logs")
        print("    ✓ terminal_log_summary - Session statistics and summaries")
        print("  ")
        print("  System Monitoring:")
        print("    ✓ system_log - Application logs and events")
        print("    ✓ log_search_query - Saved log search queries")
        print("    ✓ system_metric - Performance and system metrics")
        
        print("\n🔧 Next Steps:")
        print("  1. Start the application: python run.py")
        print("  2. Login as admin (admin/admin) or user (user/password)")
        print("  3. Scan for modules: /modules -> Scan Local Modules")
        print("  4. Browse module shop: /modules/shop")
        print("  5. Create terminal sessions: /terminal/new")
        print("  6. Monitor system logs: /admin/logs (admin only)")
        
        return True

def verify_database_health():
    """Verify database health and structure"""
    
    app = create_app()
    
    with app.app_context():
        print("\n🔍 Database Health Check:")
        
        try:
            # Test basic queries
            user_count = User.query.count()
            category_count = ModuleCategory.query.count()
            
            print(f"  ✅ Database connection: OK")
            print(f"  ✅ User table: {user_count} records")
            print(f"  ✅ Category table: {category_count} records")
            
            # Test relationships
            admin_user = User.query.filter_by(username='admin').first()
            if admin_user and admin_user.is_admin():
                print(f"  ✅ Admin user permissions: OK")
            else:
                print(f"  ❌ Admin user permissions: FAILED")
                return False
            
            # Test system log table
            SystemLog.query.count()
            print(f"  ✅ System log table: OK")
            
            # Test terminal tables
            TerminalSession.query.count()
            TerminalLog.query.count()
            print(f"  ✅ Terminal tables: OK")
            
            print(f"  ✅ Database health check: PASSED")
            return True
            
        except Exception as e:
            print(f"  ❌ Database health check: FAILED - {e}")
            return False

if __name__ == '__main__':
    try:
        # Initialize database
        if initialize_database():
            print("\n" + "=" * 50)
            
            # Verify health
            if verify_database_health():
                print("✅ Database is ready for use!")
            else:
                print("❌ Database health check failed!")
                exit(1)
        else:
            print("❌ Database initialization failed!")
            exit(1)
            
    except Exception as e:
        print(f"❌ Fatal error during database initialization: {e}")
        import traceback
        traceback.print_exc()
        exit(1)