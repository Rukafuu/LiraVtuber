mod radial;
mod studio;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(
            tauri_plugin_global_shortcut::Builder::new()
                .with_handler(move |app, _req, event| {
                    use tauri_plugin_global_shortcut::ShortcutState;
                    if event.state() == ShortcutState::Pressed {
                        let _ = radial::toggle_main_window_public(app);
                    }
                })
                .build(),
        )
        .manage(radial::init_state())
        .invoke_handler(tauri::generate_handler![
            studio::studio_salvar_arquivo,
            studio::studio_ler_arquivo,
            studio::studio_listar_arquivos_editaveis,
            studio::studio_listar_arvore,
            studio::studio_rodar_xodo,
            studio::studio_run_command,
            radial::load_config,
            radial::save_config,
            radial::run_menu_action,
            radial::open_settings_window,
            radial::hide_main_window,
            radial::hide_settings_window,
            radial::get_system_stats,
        ])
        .on_window_event(|window, event| {
            radial::on_window_event(window, event);
        })
        .setup(|app| {
            radial::setup(app)?;
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}