from pathlib import Path

# Reuse the audited v0.3.2 builder, replacing only its brittle exact-text
# signup-confirm patch with a structural slice of the actual signup_demo method.
base = Path('race-control/build_v032_subscriptions.py').read_text(encoding='utf-8')
start = base.index('# Confirm button: preserve the existing full registration')
end = base.index("\np.write_text(app, encoding='utf-8')", start)
replacement = r'''# Confirm button: structurally replace the real signup_demo confirm block.
signup_pos = app.index('    def signup_demo(self,race):')
confirm_start = app.index('        def confirm():', signup_pos)
button_start = app.index('        tk.Button(dlg,text=f"CONFIRM ENTRY', confirm_start)
button_end = app.index('\n', button_start) + 1
new_confirm = """        def confirm():
            try:
                newbal=register_with_wallet(self.conn,rider['id'],race['id'],ack.get())
                if quote['eligible'] and quote['discount']>0:
                    wallet_credit(self.conn,rider['id'],quote['discount'],kind='SUBSCRIPTION_REBATE',provider='MEMBERSHIP',note=f"{quote['plan']['name']} Community race savings")
                    record_member_use(self.conn,rider['id'],race['id'],quote)
                    newbal=wallet_balance(self.conn,rider['id'])
            except ValueError as exc:messagebox.showerror('Race Entry',str(exc),parent=dlg); return
            except Exception as exc:messagebox.showerror('Membership','Race registered, but the membership rebate could not be completed: '+str(exc),parent=dlg); return
            now=datetime.now().replace(microsecond=0).isoformat()
            self.conn.execute('INSERT INTO payment_transactions(rider_id,race_id,provider,provider_ref,amount,status,created_at) VALUES(?,?,?,?,?,?,?)',(rider['id'],race['id'],'RACE_WALLET',None,race['entry_fee'],'PAID',now)); self.conn.commit()
            dlg.destroy(); messagebox.showinfo('Gate Reserved',f"You are officially registered.\\nWallet remaining: ${newbal:,.2f}"); self.open_race_details(race['id'])
        confirm_text=f"CONFIRM MEMBER ENTRY • ${member_entry:.2f}" if quote['eligible'] else f"CONFIRM ENTRY • ${race['entry_fee']:.2f}"
        tk.Button(dlg,text=confirm_text,command=confirm,bg=GREEN if quote['eligible'] else ACCENT,fg='white',relief='flat',font=('Segoe UI Black',11),pady=10,cursor='hand2').pack(fill='x',padx=24)
"""
app = app[:confirm_start] + new_confirm + app[button_end:]
'''
patched = base[:start] + replacement + base[end:]
exec(compile(patched, 'build_v032_subscriptions_v2_runtime.py', 'exec'))
